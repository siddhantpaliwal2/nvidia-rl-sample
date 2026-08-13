#!/usr/bin/env python3
"""Package the Nemotron cohort and frozen Opus/Sol comparison traces.

The Nemotron and Opus rows are accepted only when they match the current task
checksum.  GPT-5.6 Sol is deliberately packaged as a historical comparison
cohort: its complete frontier run predates later verifier-fairness revisions,
so it is useful for trace analysis but not claimed as an exact head-to-head
score against the current task packages.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from collect_enterprise_results import redact_artifact, redact_text
from run_enterprise_daytona import (
    TASK_SNAPSHOTS,
    complete_existing,
    verifier_completion_status,
)
from run_frontier_daytona import directory_sha256
from task_paths import task_directory


ROOT = Path(__file__).resolve().parent.parent
AGENT_VERSION = "1.18.13"
TASKS = (
    "paigo-dimension-pricing-tiers",
    "paigo-top-up-billing-lifecycle",
    "paigo-s3-datastore-measurement",
    "paigo-customer-identity-migration",
    "paigo-customer-billing-schedule-migration",
    "champ-email-inbox-infrastructure",
    "finbit-bank-parser-consolidation",
    "finbit-google-cloud-storage-migration",
)
ROUTES = {
    "nemotron3-ultra": "openrouter/nvidia/nemotron-3-ultra-550b-a55b",
    "opus5": "amazon-bedrock/global.anthropic.claude-opus-5",
    "gpt56sol-historical": "openrouter/openai/gpt-5.6-sol",
}
CANDIDATE_ABORT_PROVENANCE = {
    "candidate_suite_failed_before_assertions",
    "candidate_verifier_abort",
}


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def pass_at_k(attempts: int, solves: int, k: int) -> float | None:
    if attempts < k:
        return None
    if attempts - solves < k:
        return 1.0
    return 1 - math.comb(attempts - solves, k) / math.comb(attempts, k)


def locate_trial(job_dir: Path, selected: dict) -> Path:
    for result_path in sorted(job_dir.glob("*/result.json")):
        try:
            candidate = json.loads(result_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if candidate == selected:
            return result_path.parent
    raise ValueError(f"selected result is missing below {job_dir}")


def candidate_verifier_abort(
    job_dir: Path,
    *,
    route: str,
    snapshot: str,
    checksum: str,
) -> tuple[dict, Path] | None:
    """Accept a model-caused verifier abort as a scored zero.

    Harbor's completeness helper intentionally requires one verdict per hidden
    assertion. A candidate can break compilation or crash the test process
    before the parser emits its final matrix, however. That is a real binary-
    reward failure, not an
    infrastructure retry, provided the model ran, Harbor recorded no exception,
    the verifier emitted output, and the frozen matrix metadata still matches.
    """

    metadata_path = job_dir / "matrix-metadata.json"
    root_result_path = job_dir / "result.json"
    try:
        metadata = json.loads(metadata_path.read_text())
        root_result = json.loads(root_result_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if metadata != {
        "model_route": route,
        "snapshot": snapshot,
        "agent_version": AGENT_VERSION,
        "task_sha256": checksum,
        "task_tool": "deny",
    }:
        return None
    stats = root_result.get("stats") or {}
    if stats.get("n_completed_trials") != 1 or stats.get("n_errored_trials") != 0:
        return None
    result_paths = sorted(job_dir.glob("*/result.json"))
    if len(result_paths) != 1:
        return None
    trial_dir = result_paths[0].parent
    try:
        result = json.loads(result_paths[0].read_text())
        verifier = json.loads((trial_dir / "verifier" / "output.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
    agent_result = result.get("agent_result") or {}
    stdout = trial_dir / "verifier" / "stdout.txt"
    if (
        result.get("exception_info") is not None
        or float(result.get("verifier_result", {}).get("rewards", {}).get("reward", 1))
        != 0
        or not agent_result.get("n_output_tokens")
        or not (trial_dir / "agent" / "trajectory.json").is_file()
        or not stdout.is_file()
        or not stdout.read_text(errors="replace").strip()
        or verifier.get("tests")
    ):
        return None
    return result, trial_dir


def package_artifacts(
    alias: str,
    task: str,
    attempt: int,
    trial_dir: Path,
    output_root: Path,
) -> dict:
    destination = output_root / alias / task / f"attempt-{attempt:02d}"
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    sources = {
        "result": (trial_dir / "result.json", "result.json"),
        "trajectory": (trial_dir / "agent" / "trajectory.json", "trajectory.json"),
        "verifier_output": (
            trial_dir / "verifier" / "output.json",
            "verifier-output.json",
        ),
    }
    packaged: dict[str, str] = {}
    for label, (source, name) in sources.items():
        artifact = json.loads(source.read_text())
        destination_path = destination / name
        destination_path.write_text(
            json.dumps(redact_artifact(artifact), indent=2) + "\n"
        )
        packaged[label] = str(destination_path.relative_to(ROOT))

    for source_name, destination_name, label in (
        ("stdout.txt", "verifier-stdout.txt", "verifier_stdout"),
        ("test-stdout.txt", "verifier-test-stdout.txt", "verifier_test_stdout"),
    ):
        source = trial_dir / "verifier" / source_name
        if source.is_file():
            destination_path = destination / destination_name
            destination_path.write_text(redact_text(source.read_text(errors="replace")))
            packaged[label] = str(destination_path.relative_to(ROOT))
    packaged["redaction"] = (
        "Credential assignments, provider tokens, bearer tokens, and private keys "
        "were redacted."
    )
    return packaged


def collect_trial(
    *,
    alias: str,
    task: str,
    attempt: int,
    job_dir: Path,
    expected_checksum: str,
    current_checksum: str,
    output_root: Path,
) -> dict:
    route = ROUTES[alias]
    result = complete_existing(
        job_dir,
        task,
        route=route,
        snapshot=TASK_SNAPSHOTS[task],
        agent_version=AGENT_VERSION,
        checksum=expected_checksum,
        disable_task_tool=True,
    )
    completion = None
    if result is not None:
        trial_dir = locate_trial(job_dir, result)
        completion = verifier_completion_status(trial_dir, task, result)
    else:
        aborted = candidate_verifier_abort(
            job_dir,
            route=route,
            snapshot=TASK_SNAPSHOTS[task],
            checksum=expected_checksum,
        )
        if aborted is None:
            raise ValueError(f"missing scoreable result: {job_dir.name}")
        result, trial_dir = aborted
        completion = "candidate_verifier_abort"
    if completion is None:
        raise ValueError(f"partial verifier output: {job_dir.name}")

    verifier = json.loads((trial_dir / "verifier" / "output.json").read_text())
    trajectory = json.loads((trial_dir / "agent" / "trajectory.json").read_text())
    config = json.loads((task_directory(ROOT, task) / "tests" / "config.json").read_text())
    required = config["fail_to_pass"] + config["pass_to_pass"]
    verdicts = {
        item["name"]: item["status"]
        for item in verifier.get("tests", [])
        if item.get("name")
    }
    missing = [name for name in required if name not in verdicts]
    if missing and completion not in CANDIDATE_ABORT_PROVENANCE:
        raise ValueError(
            f"{job_dir.name} does not cover {len(missing)} current assertion names"
        )
    unreported = missing if completion in CANDIDATE_ABORT_PROVENANCE else []
    if completion in CANDIDATE_ABORT_PROVENANCE:
        verdicts.update({name: "failed" for name in missing})

    steps = trajectory.get("steps") or []
    reward = float(result["verifier_result"]["rewards"]["reward"])
    agent_result = result.get("agent_result") or {}
    artifacts = package_artifacts(alias, task, attempt, trial_dir, output_root)
    return {
        "attempt": attempt,
        "task": task,
        "job": job_dir.name,
        "route": route,
        "agent": f"OpenCode {AGENT_VERSION}",
        "task_sha256": expected_checksum,
        "current_task_sha256": current_checksum,
        "checksum_relation": (
            "exact-current" if expected_checksum == current_checksum else "historical"
        ),
        "reward": reward,
        "passed_required_tests": sum(
            verdicts.get(name) == "passed" for name in required
        ),
        "total_required_tests": len(required),
        "failed_required_tests": [
            name for name in required if verdicts.get(name) != "passed"
        ],
        "unreported_required_tests": unreported,
        "model_turns": sum(step.get("source") == "agent" for step in steps),
        "tool_calls": sum(len(step.get("tool_calls") or []) for step in steps),
        "agent_wall_time_seconds": round(
            (
                parse_timestamp(result["agent_execution"]["finished_at"])
                - parse_timestamp(result["agent_execution"]["started_at"])
            ).total_seconds(),
            3,
        ),
        "trial_wall_time_seconds": round(
            (
                parse_timestamp(result["finished_at"])
                - parse_timestamp(result["started_at"])
            ).total_seconds(),
            3,
        ),
        "cost_usd": round(float(agent_result.get("cost_usd") or 0), 6),
        "input_tokens": agent_result.get("n_input_tokens"),
        "cache_tokens": agent_result.get("n_cache_tokens"),
        "output_tokens": agent_result.get("n_output_tokens"),
        "grading_provenance": completion,
        "artifacts": artifacts,
    }


def current_opus_jobs(source_raw: Path, task: str, checksum: str) -> list[Path]:
    candidates: list[tuple[datetime, Path]] = []
    for job_dir in source_raw.iterdir():
        if not job_dir.is_dir() or f"-{task}-a" not in job_dir.name:
            continue
        metadata_path = job_dir / "matrix-metadata.json"
        try:
            metadata = json.loads(metadata_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if (
            metadata.get("model_route") != ROUTES["opus5"]
            or metadata.get("task_sha256") != checksum
        ):
            continue
        result = complete_existing(
            job_dir,
            task,
            route=ROUTES["opus5"],
            snapshot=TASK_SNAPSHOTS[task],
            agent_version=AGENT_VERSION,
            checksum=checksum,
            disable_task_tool=True,
        )
        if result is None:
            continue
        trial_dir = locate_trial(job_dir, result)
        if verifier_completion_status(trial_dir, task, result) is None:
            continue
        candidates.append((parse_timestamp(result["started_at"]), job_dir))
    candidates.sort(key=lambda item: (item[0], item[1].name))
    selected = [item[1] for item in candidates[:4]]
    if len(selected) != 4:
        raise ValueError(f"expected four current-checksum Opus trials for {task}")
    return selected


def nemotron_jobs(nvidia_raw: Path, task: str, checksum: str) -> list[Path]:
    candidates: list[tuple[int, Path]] = []
    prefix = f"nvidia-nemotron3-ultra-final4-r1-nemotron3-ultra-{task}-a"
    for job_dir in nvidia_raw.glob(f"{prefix}*"):
        try:
            attempt = int(job_dir.name.removeprefix(prefix))
        except ValueError:
            continue
        result = complete_existing(
            job_dir,
            task,
            route=ROUTES["nemotron3-ultra"],
            snapshot=TASK_SNAPSHOTS[task],
            agent_version=AGENT_VERSION,
            checksum=checksum,
            disable_task_tool=True,
        )
        if result is None and candidate_verifier_abort(
            job_dir,
            route=ROUTES["nemotron3-ultra"],
            snapshot=TASK_SNAPSHOTS[task],
            checksum=checksum,
        ) is None:
            continue
        candidates.append((attempt, job_dir))
    candidates.sort()
    selected = [item[1] for item in candidates[:4]]
    if len(selected) != 4:
        raise ValueError(f"expected four model-executed Nemotron trials for {task}")
    return selected


def historical_sol_jobs(source_raw: Path, task: str) -> list[Path]:
    jobs = [
        source_raw / f"enterprise-exact-frontier-r1-gpt56sol-{task}-a{attempt:02d}"
        for attempt in range(1, 9)
    ]
    current_required = set(
        json.loads((task_directory(ROOT, task) / "tests" / "config.json").read_text())[
            "fail_to_pass"
        ]
        + json.loads(
            (task_directory(ROOT, task) / "tests" / "config.json").read_text()
        )["pass_to_pass"]
    )
    complete: list[Path] = []
    for job_dir in jobs:
        result_paths = sorted(job_dir.glob("*/result.json"))
        if not result_paths:
            continue
        verifier = json.loads(
            (result_paths[0].parent / "verifier" / "output.json").read_text()
        )
        observed = {
            item.get("name") for item in verifier.get("tests", []) if item.get("name")
        }
        if current_required <= observed:
            complete.append(job_dir)
    if len(complete) < 4:
        raise ValueError(f"fewer than four complete historical Sol trials for {task}")
    return complete[:4]


def summarize_model(alias: str, attempts: list[dict], quantitative: bool) -> dict:
    task_results = []
    for task in TASKS:
        rows = [item for item in attempts if item["task"] == task]
        solves = sum(item["reward"] == 1 for item in rows)
        failed = Counter(
            name for item in rows for name in item["failed_required_tests"]
        )
        task_results.append(
            {
                "task": task,
                "solves": solves,
                "attempts": len(rows),
                "pass_at_1": round(solves / len(rows), 6),
                "pass_at_4": pass_at_k(len(rows), solves, 4),
                "required_tests_passed": sum(
                    item["passed_required_tests"] for item in rows
                ),
                "required_tests_total": sum(
                    item["total_required_tests"] for item in rows
                ),
                "required_test_pass_rate": round(
                    sum(item["passed_required_tests"] for item in rows)
                    / sum(item["total_required_tests"] for item in rows),
                    6,
                ),
                "median_tool_calls": statistics.median(
                    item["tool_calls"] for item in rows
                ),
                "mean_trial_wall_time_seconds": round(
                    statistics.mean(item["trial_wall_time_seconds"] for item in rows),
                    3,
                ),
                "cost_usd": round(sum(item["cost_usd"] for item in rows), 6),
                "recurring_failures": [
                    {"test": name, "count": count}
                    for name, count in failed.most_common()
                ],
                "results": rows,
            }
        )
    solves = sum(item["reward"] == 1 for item in attempts)
    required_passed = sum(item["passed_required_tests"] for item in attempts)
    required_total = sum(item["total_required_tests"] for item in attempts)
    return {
        "alias": alias,
        "route": ROUTES[alias],
        "comparison_status": (
            "quantitative-current-checksum"
            if quantitative
            else "qualitative-historical-checksum"
        ),
        "solves": solves,
        "attempts": len(attempts),
        "macro_pass_at_1": round(
            statistics.mean(item["pass_at_1"] for item in task_results), 6
        ),
        "macro_pass_at_4": round(
            statistics.mean(item["pass_at_4"] for item in task_results), 6
        ),
        "tasks_solved_at_least_once": sum(
            item["solves"] > 0 for item in task_results
        ),
        "required_tests_passed": required_passed,
        "required_tests_total": required_total,
        "required_test_pass_rate": round(required_passed / required_total, 6),
        "model_turns": sum(item["model_turns"] for item in attempts),
        "tool_calls": sum(item["tool_calls"] for item in attempts),
        "median_tool_calls": statistics.median(
            item["tool_calls"] for item in attempts
        ),
        "mean_agent_wall_time_seconds": round(
            statistics.mean(item["agent_wall_time_seconds"] for item in attempts), 3
        ),
        "mean_trial_wall_time_seconds": round(
            statistics.mean(item["trial_wall_time_seconds"] for item in attempts), 3
        ),
        "cost_usd": round(sum(item["cost_usd"] for item in attempts), 6),
        "task_results": task_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-repo",
        type=Path,
        default=ROOT.parent / "xai-rl-sample",
    )
    args = parser.parse_args()
    source = args.source_repo.resolve()
    source_raw = source / "sample-run" / "enterprise-raw"
    nvidia_raw = source / "sample-run" / "nvidia-raw"
    output_root = ROOT / "sample-run" / "trials"
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    current_checksums = {
        task: directory_sha256(task_directory(ROOT, task)) for task in TASKS
    }
    collected: dict[str, list[dict]] = {alias: [] for alias in ROUTES}

    for task in TASKS:
        current = current_checksums[task]
        for attempt, job in enumerate(
            nemotron_jobs(nvidia_raw, task, current), start=1
        ):
            collected["nemotron3-ultra"].append(
                collect_trial(
                    alias="nemotron3-ultra",
                    task=task,
                    attempt=attempt,
                    job_dir=job,
                    expected_checksum=current,
                    current_checksum=current,
                    output_root=output_root,
                )
            )

        for attempt, job in enumerate(
            current_opus_jobs(source_raw, task, current), start=1
        ):
            collected["opus5"].append(
                collect_trial(
                    alias="opus5",
                    task=task,
                    attempt=attempt,
                    job_dir=job,
                    expected_checksum=current,
                    current_checksum=current,
                    output_root=output_root,
                )
            )

        for attempt, job in enumerate(historical_sol_jobs(source_raw, task), start=1):
            metadata = json.loads((job / "matrix-metadata.json").read_text())
            collected["gpt56sol-historical"].append(
                collect_trial(
                    alias="gpt56sol-historical",
                    task=task,
                    attempt=attempt,
                    job_dir=job,
                    expected_checksum=metadata["task_sha256"],
                    current_checksum=current,
                    output_root=output_root,
                )
            )

    models = [
        summarize_model("nemotron3-ultra", collected["nemotron3-ultra"], True),
        summarize_model("opus5", collected["opus5"], True),
        summarize_model(
            "gpt56sol-historical", collected["gpt56sol-historical"], False
        ),
    ]
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "experiment": {
            "tasks": list(TASKS),
            "nemotron_rollouts_per_task": 4,
            "agent": f"OpenCode {AGENT_VERSION}",
            "environment": "one isolated Daytona sandbox per attempt",
            "task_tool": "denied",
            "reward": "binary; every fail_to_pass and pass_to_pass assertion must pass",
        },
        "comparison_policy": {
            "quantitative": (
                "Nemotron 3 Ultra and Claude Opus 5 use the exact current task "
                "checksums, model routes, agent version, snapshots, and verifier policy."
            ),
            "historical": (
                "GPT-5.6 Sol uses four complete traces per task from the earlier "
                "frontier checkpoint. All current assertion names are present, but "
                "task checksums predate fairness revisions; use these traces for "
                "qualitative win-condition analysis, not an exact score claim."
            ),
        },
        "models": models,
    }
    output_path = ROOT / "sample-run" / "results.json"
    output_path.write_text(json.dumps(output, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "trials": {alias: len(rows) for alias, rows in collected.items()},
                "solves": {
                    item["alias"]: f"{item['solves']}/{item['attempts']}"
                    for item in models
                },
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
