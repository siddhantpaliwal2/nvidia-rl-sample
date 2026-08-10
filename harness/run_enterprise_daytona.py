#!/usr/bin/env python3
"""Run staged enterprise-task rollouts on Daytona with a hard spend guard.

The runner deliberately supports small stages. Start with one attempt per
model/task, inspect validity and difficulty, and only then extend pass@k.
Completed cells are reused only when task checksum, model route, agent version,
snapshot, and single-agent policy all match.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from run_frontier_daytona import (
    DENIED_TASK_CONFIG,
    directory_sha256,
    parse_model,
    valid_existing,
)


ROOT = Path(__file__).resolve().parent.parent
TASK_SNAPSHOTS = {
    "paigo-dimension-pricing-tiers": "harbor-probe-paigo-dimension-pricing-tiers-8g",
    "paigo-top-up-billing-lifecycle": "harbor-probe-paigo-top-up-billing-lifecycle-8g",
    "paigo-s3-datastore-measurement": "harbor-probe-paigo-s3-datastore-measurement-8g",
    "paigo-customer-identity-migration": "harbor-probe-paigo-customer-identity-migration-8g",
    "paigo-customer-billing-schedule-migration": "harbor-probe-paigo-customer-billing-schedule-migration-8g",
    "finbit-bank-parser-consolidation": "harbor-probe-finbit-bank-parser-consolidation-8g",
    "finbit-google-cloud-storage-migration": "harbor-probe-finbit-google-cloud-storage-migration-8g",
    "champ-email-inbox-infrastructure": "harbor-probe-champ-email-inbox-infrastructure-8g",
}
DEFAULT_MODELS = {
    "opus5-bedrock": "amazon-bedrock/global.anthropic.claude-opus-5",
}
PRINT_LOCK = threading.Lock()


def emit(message: str) -> None:
    with PRINT_LOCK:
        print(message, flush=True)


def trial_payload(job_dir: Path) -> tuple[dict, dict] | None:
    for result_path in sorted(job_dir.glob("*/result.json")):
        try:
            result = json.loads(result_path.read_text())
            verifier = json.loads(
                (result_path.parent / "verifier" / "output.json").read_text()
            )
            trajectory = json.loads(
                (result_path.parent / "agent" / "trajectory.json").read_text()
            )
        except (OSError, json.JSONDecodeError):
            continue
        reward = ((result.get("verifier_result") or {}).get("rewards") or {}).get(
            "reward"
        )
        if (
            result.get("exception_info") is None
            and reward is not None
            and verifier.get("tests")
            and trajectory.get("steps")
        ):
            return result, trajectory
    return None


def result_metrics(result: dict) -> dict:
    agent_result = result.get("agent_result") or {}
    reward = ((result.get("verifier_result") or {}).get("rewards") or {}).get(
        "reward"
    )
    return {
        "reward": reward,
        "cost_usd": float(agent_result.get("cost_usd") or 0),
        "input_tokens": agent_result.get("n_input_tokens"),
        "cache_tokens": agent_result.get("n_cache_tokens"),
        "output_tokens": agent_result.get("n_output_tokens"),
    }


def recorded_spend(ledger: Path) -> float:
    if not ledger.is_file():
        return 0.0
    total = 0.0
    for line in ledger.read_text().splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("event") in {"completed", "invalid"}:
            total += float(item.get("cost_usd") or 0)
    return total


def append_ledger(ledger: Path, item: dict) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a") as handle:
        handle.write(json.dumps(item, sort_keys=True) + "\n")


def complete_existing(
    job_dir: Path,
    task: str,
    *,
    route: str,
    snapshot: str,
    agent_version: str,
    checksum: str,
    disable_task_tool: bool,
) -> dict | None:
    """Return a reusable result when its verifier outcome is scoreable.

    Harbor can still emit a syntactically valid result when Jest or Gradle
    aborts after collecting only part of the requested suite. Silent partial
    output is not scoreable. An explicit candidate-caused suite-load failure,
    however, is a legitimate zero rather than an infrastructure retry.
    """
    result = valid_existing(
        job_dir,
        route=route,
        snapshot=snapshot,
        agent_version=agent_version,
        checksum=checksum,
        disable_task_tool=disable_task_tool,
    )
    if result is None:
        return None

    for result_path in sorted(job_dir.glob("*/result.json")):
        try:
            candidate = json.loads(result_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if candidate != result:
            continue
        status = verifier_completion_status(result_path.parent, task, candidate)
        return result if status is not None else None
    return None


def verifier_completion_status(trial_dir: Path, task: str, result: dict) -> str | None:
    """Classify complete output or an attributable candidate suite-load failure."""

    try:
        config = json.loads(
            (ROOT / "tasks" / task / "tests" / "config.json").read_text()
        )
        verifier = json.loads((trial_dir / "verifier" / "output.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None

    required = set(config["fail_to_pass"]) | set(config["pass_to_pass"])
    observed = {
        test.get("name") for test in verifier.get("tests", []) if test.get("name")
    }
    if required <= observed:
        return "complete_verifier_output"

    reward = result.get("verifier_result", {}).get("rewards", {}).get("reward")
    stdout_paths = (
        trial_dir / "verifier" / "test-stdout.txt",
        trial_dir / "verifier" / "stdout.txt",
    )
    stdout = "\n".join(
        path.read_text(errors="replace") for path in stdout_paths if path.is_file()
    )
    if reward == 0 and "Test suite failed to run" in stdout:
        return "candidate_suite_failed_before_assertions"
    return None


def run_one(
    alias: str,
    route: str,
    task: str,
    attempt: int,
    *,
    env_file: Path,
    jobs_dir: Path,
    logs_dir: Path,
    run_id: str,
    agent_version: str,
    retries: int,
    job_timeout: int,
) -> dict:
    snapshot = TASK_SNAPSHOTS[task]
    checksum = directory_sha256(ROOT / "tasks" / task)
    job_name = f"{run_id}-{alias}-{task}-a{attempt:02d}"
    job_dir = jobs_dir / job_name
    existing = complete_existing(
        job_dir,
        task,
        route=route,
        snapshot=snapshot,
        agent_version=agent_version,
        checksum=checksum,
        disable_task_tool=True,
    )
    if existing is not None:
        metrics = result_metrics(existing)
        emit(f"REUSE {job_name} reward={metrics['reward']} cost=${metrics['cost_usd']:.2f}")
        return {"job": job_name, "status": "reused", **metrics}

    opencode_config = json.dumps(DENIED_TASK_CONFIG, separators=(",", ":"))
    if route == "openai/openai.gpt-5.6-sol":
        raise ValueError(
            "GPT-5.6 Sol's Mantle endpoint and authenticated relays are blocked "
            "by the current Daytona network tier; use an exact Sol provider "
            "route already allowed by Daytona"
        )
    command = [
        "harbor",
        "run",
        "-p",
        f"tasks/{task}",
        "-e",
        "daytona",
        "--ek",
        f"snapshot_template_name={snapshot}",
        "--ek",
        "assume_global_snapshot=true",
        "-a",
        "harness.harbor_agents:OpenCodeNode22",
        "-m",
        route,
        "--ak",
        f"version={agent_version}",
        "--ak",
        f"opencode_config={opencode_config}",
        "--env-file",
        str(env_file),
        "-k",
        "1",
        "-n",
        "1",
        "-o",
        str(jobs_dir),
        "--job-name",
        job_name,
        "-q",
        "-y",
    ]
    metadata = {
        "model_route": route,
        "snapshot": snapshot,
        "agent_version": agent_version,
        "task_sha256": checksum,
        "task_tool": "deny",
    }
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{job_name}.log"

    for retry in range(retries + 1):
        if job_dir.exists():
            shutil.rmtree(job_dir)
        emit(f"START {job_name} try={retry + 1}")
        with log_path.open("a") as log:
            completed = subprocess.run(
                command,
                cwd=ROOT,
                env={
                    **os.environ,
                    "PYTHONPATH": str(ROOT)
                    + (f":{os.environ['PYTHONPATH']}" if os.environ.get('PYTHONPATH') else ""),
                },
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=job_timeout,
                check=False,
            )
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "matrix-metadata.json").write_text(
            json.dumps(metadata, indent=2) + "\n"
        )
        existing = complete_existing(
            job_dir,
            task,
            route=route,
            snapshot=snapshot,
            agent_version=agent_version,
            checksum=checksum,
            disable_task_tool=True,
        )
        if existing is not None:
            metrics = result_metrics(existing)
            emit(f"DONE  {job_name} reward={metrics['reward']} cost=${metrics['cost_usd']:.2f}")
            return {
                "job": job_name,
                "status": "completed",
                "returncode": completed.returncode,
                **metrics,
            }
        tail = log_path.read_text(errors="replace")[-12000:].lower()
        fatal = (
            "insufficient credits",
            "authenticationerror",
            "invalid api key",
            "model not found",
            "invalid model",
            "opencode: command not found",
        )
        if any(marker in tail for marker in fatal):
            break
        emit(f"RETRY {job_name} returncode={completed.returncode}")
    unscored = valid_existing(
        job_dir,
        route=route,
        snapshot=snapshot,
        agent_version=agent_version,
        checksum=checksum,
        disable_task_tool=True,
    )
    if unscored is not None:
        metrics = result_metrics(unscored)
        emit(f"INVALID {job_name} cost=${metrics['cost_usd']:.2f}")
        return {
            "job": job_name,
            "status": "invalid",
            "reward": None,
            **{key: value for key, value in metrics.items() if key != "reward"},
        }
    emit(f"FAILED {job_name}")
    return {"job": job_name, "status": "failed", "reward": None, "cost_usd": 0.0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--model", action="append", type=parse_model)
    parser.add_argument("--task", action="append", choices=tuple(TASK_SNAPSHOTS))
    parser.add_argument("--attempt-start", type=int, default=1)
    parser.add_argument("--attempts", type=int, default=1)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--agent-version", default="1.18.13")
    parser.add_argument("--job-timeout", type=int, default=9000)
    parser.add_argument("--run-id", default="enterprise-smoke-r1")
    parser.add_argument(
        "--jobs-dir", type=Path, default=ROOT / "sample-run" / "enterprise-raw"
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=ROOT / "sample-run" / "enterprise-budget-ledger.jsonl",
    )
    parser.add_argument("--reserve-per-trial", type=float, default=100.0)
    parser.add_argument("--target-budget", type=float, default=2000.0)
    parser.add_argument("--hard-budget", type=float, default=3000.0)
    args = parser.parse_args()

    env_file = args.env_file.expanduser().resolve()
    if not env_file.is_file():
        parser.error(f"env file does not exist: {env_file}")
    if min(args.attempt_start, args.attempts, args.concurrency, args.job_timeout) < 1:
        parser.error("attempt, concurrency, and timeout values must be positive")
    if args.retries < 0 or args.reserve_per_trial <= 0:
        parser.error("retries cannot be negative and reserve must be positive")
    if args.target_budget > args.hard_budget:
        parser.error("target budget cannot exceed hard budget")

    models = dict(args.model or DEFAULT_MODELS.items())
    if len(models) != len(args.model or DEFAULT_MODELS):
        parser.error("model aliases must be unique")
    tasks = args.task or list(TASK_SNAPSHOTS)
    jobs = [
        (alias, route, task, attempt)
        for attempt in range(args.attempt_start, args.attempt_start + args.attempts)
        for task in tasks
        for alias, route in models.items()
    ]
    ledger = args.ledger.resolve()
    spent = recorded_spend(ledger)
    reserved = args.reserve_per_trial * len(jobs)
    if spent + reserved > args.hard_budget:
        parser.error(
            f"hard budget guard: spent ${spent:.2f} + reserve ${reserved:.2f} "
            f"> ${args.hard_budget:.2f}"
        )
    if spent + reserved > args.target_budget:
        emit(
            f"WARNING projected reservation ${spent + reserved:.2f} exceeds "
            f"target ${args.target_budget:.2f}"
        )
    emit(
        f"Enterprise stage: {len(jobs)} trials, spent=${spent:.2f}, "
        f"reserved=${reserved:.2f}, hard=${args.hard_budget:.2f}"
    )

    jobs_dir = args.jobs_dir.resolve()
    logs_dir = ROOT / "sample-run" / "enterprise-runner-logs"
    outcomes: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(
                run_one,
                alias,
                route,
                task,
                attempt,
                env_file=env_file,
                jobs_dir=jobs_dir,
                logs_dir=logs_dir,
                run_id=args.run_id,
                agent_version=args.agent_version,
                retries=args.retries,
                job_timeout=args.job_timeout,
            ): (alias, route, task, attempt)
            for alias, route, task, attempt in jobs
        }
        for future in as_completed(futures):
            alias, route, task, attempt = futures[future]
            try:
                outcome = future.result()
            except Exception as exc:  # noqa: BLE001
                outcome = {
                    "job": f"{args.run_id}-{alias}-{task}-a{attempt:02d}",
                    "status": "failed",
                    "reward": None,
                    "cost_usd": 0.0,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            outcome.update(
                {
                    "alias": alias,
                    "model_route": route,
                    "task": task,
                    "attempt": attempt,
                }
            )
            outcomes.append(outcome)
            if outcome["status"] in {"completed", "invalid"} and float(
                outcome.get("cost_usd") or 0
            ) > 0:
                append_ledger(
                    ledger,
                    {
                        "event": outcome["status"],
                        "recorded_at": datetime.now(timezone.utc).isoformat(),
                        **outcome,
                    },
                )

    outcomes.sort(key=lambda item: item["job"])
    summary = ROOT / "sample-run" / f"enterprise-run-summary-{args.run_id}.json"
    summary.write_text(json.dumps(outcomes, indent=2) + "\n")
    valid = [item for item in outcomes if item.get("reward") is not None]
    cost = sum(float(item.get("cost_usd") or 0) for item in outcomes)
    emit(f"SUMMARY valid={len(valid)}/{len(outcomes)} stage_cost=${cost:.2f}")
    return 0 if len(valid) == len(outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
