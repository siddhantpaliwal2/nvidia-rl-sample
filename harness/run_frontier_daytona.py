#!/usr/bin/env python3
"""Run a resumable OpenCode model matrix on the Daytona task bank.

One global worker pool caps aggregate Daytona usage across every requested
model and task. A prior cell is reused only when its graded result, requested
route, OpenCode version, snapshot, and task-content checksum all match.

Example:
    python harness/run_frontier_daytona.py \
      --env-file /tmp/xai-rl-daytona.env \
      --model opus5=openrouter/anthropic/claude-opus-5 \
      --model fable5=openrouter/anthropic/claude-fable-5 \
      --attempts 3 --concurrency 12 --run-id existing8-r1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODELS = {
    "opus5": "openrouter/anthropic/claude-opus-5",
    "fable5": "openrouter/anthropic/claude-fable-5",
}
TASK_SNAPSHOTS = {
    "latent-credit-normalize": "harbor-probe-latent-credit-normalize-4g",
    "latent-doc-extractors": "harbor-probe-latent-doc-extractors-4g",
    "latent-financial-tools": "harbor-probe-latent-financial-tools-4g",
    "latent-phone-invites": "harbor-probe-latent-phone-invites-4g",
    "xrepo-fiu-latent": "harbor-probe-xrepo-fiu-latent-4g",
    "xrepo-txenrich-latent": "harbor-probe-xrepo-txenrich-latent-4g",
    "xrepo-txenrich3-latent": "harbor-probe-xrepo-txenrich3-latent-4g",
    "xrepo-txenrich4-latent": "harbor-probe-xrepo-txenrich4-latent-4g",
    "long-native-table-migration": "harbor-probe-long-native-table-migration-4g",
}
DEFAULT_TASKS = tuple(
    task for task in TASK_SNAPSHOTS if task != "long-native-table-migration"
)
PRINT_LOCK = threading.Lock()
DENIED_TASK_CONFIG = {"permission": {"task": "deny"}}


def emit(message: str) -> None:
    with PRINT_LOCK:
        print(message, flush=True)


def directory_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    for file_path in sorted(
        item
        for item in path.rglob("*")
        if item.is_file()
        and "__pycache__" not in item.parts
        and item.suffix not in {".pyc", ".pyo"}
        and item.name != ".DS_Store"
    ):
        digest.update(str(file_path.relative_to(path)).encode())
        digest.update(b"\0")
        digest.update(file_path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def parse_model(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("models must use ALIAS=ROUTE")
    alias, route = value.split("=", 1)
    if not alias or not route or not alias.replace("-", "").isalnum():
        raise argparse.ArgumentTypeError(f"invalid model specification: {value}")
    return alias, route


def task_tool_is_denied(value: object) -> bool:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return False
    return value == DENIED_TASK_CONFIG


def trial_artifacts(job_dir: Path) -> tuple[Path, dict, dict] | None:
    for result_path in sorted(job_dir.glob("*/result.json")):
        try:
            result = json.loads(result_path.read_text())
            trajectory = json.loads(
                (result_path.parent / "agent" / "trajectory.json").read_text()
            )
            verifier = json.loads(
                (result_path.parent / "verifier" / "output.json").read_text()
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
            return result_path.parent, result, trajectory
    return None


def valid_existing(
    job_dir: Path,
    *,
    route: str,
    snapshot: str,
    agent_version: str,
    checksum: str,
    disable_task_tool: bool,
) -> dict | None:
    metadata_path = job_dir / "matrix-metadata.json"
    found = trial_artifacts(job_dir)
    if found is None or not metadata_path.is_file():
        return None
    try:
        metadata = json.loads(metadata_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    _, result, trajectory = found
    config = result.get("config") or {}
    agent = config.get("agent") or {}
    environment = config.get("environment") or {}
    environment_kwargs = environment.get("kwargs") or {}
    trajectory_agent = trajectory.get("agent") or {}
    expected = {
        "model_route": route,
        "snapshot": snapshot,
        "agent_version": agent_version,
        "task_sha256": checksum,
    }
    if disable_task_tool:
        expected["task_tool"] = "deny"
    if metadata != expected:
        return None
    if agent.get("model_name") != route:
        return None
    if trajectory_agent.get("model_name") != route:
        return None
    if str(trajectory_agent.get("version")) != agent_version:
        return None
    if disable_task_tool:
        if not task_tool_is_denied(
            (agent.get("kwargs") or {}).get("opencode_config")
        ):
            return None
    if environment_kwargs.get("snapshot_template_name") != snapshot:
        return None
    return result


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
    disable_task_tool: bool,
    job_timeout: int,
) -> dict:
    snapshot = TASK_SNAPSHOTS[task]
    checksum = directory_sha256(ROOT / "tasks" / task)
    job_name = f"{run_id}-{alias}-{task}-a{attempt:02d}"
    job_dir = jobs_dir / job_name
    existing = valid_existing(
        job_dir,
        route=route,
        snapshot=snapshot,
        agent_version=agent_version,
        checksum=checksum,
        disable_task_tool=disable_task_tool,
    )
    if existing is not None:
        reward = existing["verifier_result"]["rewards"]["reward"]
        emit(f"REUSE {job_name} reward={reward}")
        return {"job": job_name, "status": "reused", "reward": reward}

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
        "opencode",
        "-m",
        route,
        "--ak",
        f"version={agent_version}",
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
    }
    if disable_task_tool:
        opencode_config = json.dumps(
            DENIED_TASK_CONFIG, separators=(",", ":")
        )
        command[command.index("--env-file"):command.index("--env-file")] = [
            "--ak",
            f"opencode_config={opencode_config}",
        ]
        metadata["task_tool"] = "deny"
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
        result = valid_existing(
            job_dir,
            route=route,
            snapshot=snapshot,
            agent_version=agent_version,
            checksum=checksum,
            disable_task_tool=disable_task_tool,
        )
        if result is not None:
            reward = result["verifier_result"]["rewards"]["reward"]
            emit(f"DONE  {job_name} reward={reward}")
            return {
                "job": job_name,
                "status": "completed",
                "reward": reward,
                "returncode": completed.returncode,
            }
        log_text = log_path.read_text(errors="replace")[-12000:].lower()
        fatal_markers = (
            "insufficient credits",
            "authenticationerror",
            "invalid api key",
            "model not found",
            "invalid model",
        )
        if any(marker in log_text for marker in fatal_markers):
            emit(f"FATAL {job_name} returncode={completed.returncode}")
            break
        emit(f"RETRY {job_name} returncode={completed.returncode}")

    emit(f"FAILED {job_name}")
    return {"job": job_name, "status": "failed", "reward": None}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument(
        "--model",
        action="append",
        type=parse_model,
        help="ALIAS=ROUTE; repeat for multiple models (defaults to Opus 5 and Fable 5)",
    )
    parser.add_argument("--task", action="append", choices=tuple(TASK_SNAPSHOTS))
    parser.add_argument(
        "--attempt-start",
        type=int,
        default=1,
        help="first provider-attempt number (useful for infrastructure supplements)",
    )
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=12)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--agent-version", default="1.18.13")
    parser.add_argument(
        "--disable-task-tool",
        action="store_true",
        help="deny OpenCode's subagent task tool for a single-agent evaluation",
    )
    parser.add_argument("--job-timeout", type=int, default=5400)
    parser.add_argument("--run-id", default="existing8-r1")
    parser.add_argument(
        "--jobs-dir", type=Path, default=ROOT / "sample-run" / "frontier-raw"
    )
    args = parser.parse_args()

    env_file = args.env_file.expanduser().resolve()
    if not env_file.is_file():
        parser.error(f"env file does not exist: {env_file}")
    if (
        args.concurrency < 1
        or args.attempt_start < 1
        or args.attempts < 1
        or args.retries < 0
        or args.job_timeout < 1
    ):
        parser.error(
            "concurrency, attempt-start, and attempts must be positive; "
            "retries cannot be negative"
        )
    models = dict(args.model or DEFAULT_MODELS.items())
    if len(models) != len(args.model or DEFAULT_MODELS):
        parser.error("model aliases must be unique")
    # The long-horizon gate is a separate screen with a different attempt
    # budget. Include it only when the caller names it explicitly.
    tasks = args.task or list(DEFAULT_TASKS)
    jobs_dir = args.jobs_dir.resolve()
    logs_dir = ROOT / "sample-run" / "frontier-runner-logs"
    jobs = [
        (alias, route, task, attempt)
        for attempt in range(args.attempt_start, args.attempt_start + args.attempts)
        for task in tasks
        for alias, route in models.items()
    ]
    emit(
        f"Frontier matrix: {len(jobs)} trials, models={','.join(models)}, "
        f"Daytona concurrency={args.concurrency}"
    )

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
                disable_task_tool=args.disable_task_tool,
                job_timeout=args.job_timeout,
            ): (alias, task, attempt)
            for alias, route, task, attempt in jobs
        }
        for future in as_completed(futures):
            alias, task, attempt = futures[future]
            try:
                outcomes.append(future.result())
            except Exception as exc:  # noqa: BLE001
                emit(f"ERROR {alias}-{task}-a{attempt:02d}: {type(exc).__name__}: {exc}")
                outcomes.append(
                    {
                        "job": f"{args.run_id}-{alias}-{task}-a{attempt:02d}",
                        "status": "failed",
                        "reward": None,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

    outcomes.sort(key=lambda item: item["job"])
    summary_path = ROOT / "sample-run" / f"frontier-run-summary-{args.run_id}.json"
    summary_path.write_text(json.dumps(outcomes, indent=2) + "\n")
    failures = [item for item in outcomes if item["reward"] is None]
    emit(f"SUMMARY valid={len(outcomes) - len(failures)} failed={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
