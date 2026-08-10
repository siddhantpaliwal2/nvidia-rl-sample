#!/usr/bin/env python3
"""Collect only final-checksum enterprise calibration attempts."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from run_enterprise_daytona import (
    TASK_SNAPSHOTS,
    complete_existing,
    recorded_spend,
    verifier_completion_status,
)
from run_frontier_daytona import directory_sha256


ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "sample-run" / "enterprise-raw"
LEDGER = ROOT / "sample-run" / "enterprise-budget-ledger.jsonl"
OUTPUT = ROOT / "sample-run" / "enterprise-model-results.json"
PACKAGED = ROOT / "sample-run" / "enterprise-trials"
AGENT_VERSION = "1.18.13"
SENSITIVE_ASSIGNMENT = re.compile(
    r"(?im)^(\s*[A-Z_][A-Z0-9_.-]*(?:KEY|SECRET|PASSWORD|TOKEN|CREDENTIAL)"
    r"[A-Z0-9_.-]*\s*=)[^\r\n]*"
)
SENSITIVE_TOKEN_PATTERNS = (
    re.compile(r"sk-or-v1-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?:AKIA|ASIA)[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9._-]{3,8}~[A-Za-z0-9._-]{20,}"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._~+/-]{20,}=*"),
    re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----.*?"
        r"-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
        re.DOTALL,
    ),
)
OPUS_A01 = {
    "paigo-dimension-pricing-tiers": (
        "enterprise-opus-pricing-final-r1-opus5-bedrock-"
        "paigo-dimension-pricing-tiers-a01"
    ),
    "paigo-top-up-billing-lifecycle": (
        "enterprise-opus-final-a01-r1-opus5-bedrock-"
        "paigo-top-up-billing-lifecycle-a01"
    ),
    "paigo-s3-datastore-measurement": (
        "enterprise-opus-final-a01-r1-opus5-bedrock-"
        "paigo-s3-datastore-measurement-a01"
    ),
    "paigo-customer-identity-migration": (
        "enterprise-opus-reserved-tests-r1-opus5-bedrock-"
        "paigo-customer-identity-migration-a01"
    ),
    "paigo-customer-billing-schedule-migration": (
        "enterprise-opus-final-taxonomy-r1-opus5-bedrock-"
        "paigo-customer-billing-schedule-migration-a01"
    ),
    "champ-email-inbox-infrastructure": (
        "enterprise-opus-fair-complete-r1-opus5-bedrock-"
        "champ-email-inbox-infrastructure-a01"
    ),
    "finbit-bank-parser-consolidation": (
        "enterprise-opus-final-a01-r1-opus5-bedrock-"
        "finbit-bank-parser-consolidation-a01"
    ),
    "finbit-google-cloud-storage-migration": (
        "enterprise-opus-cloud-fair-r1-opus5-bedrock-"
        "finbit-google-cloud-storage-migration-a01"
    ),
}
OPUS_JOBS = {
    task: [
        first_job,
        *(
            (
                f"enterprise-opus-pricing-final-r1-opus5-bedrock-{task}-a{attempt:02d}"
                if task == "paigo-dimension-pricing-tiers"
                else f"enterprise-opus-final-a23-r1-opus5-bedrock-{task}-a{attempt:02d}"
            )
            for attempt in (2, 3)
        ),
        *(
            f"enterprise-opus-final-a48-r1-opus5-bedrock-{task}-a{attempt:02d}"
            for attempt in range(4, 9)
        ),
    ]
    for task, first_job in OPUS_A01.items()
}
RECALIBRATED_TASKS = {
    "paigo-dimension-pricing-tiers",
    "paigo-top-up-billing-lifecycle",
    "paigo-s3-datastore-measurement",
    "paigo-customer-identity-migration",
    "finbit-bank-parser-consolidation",
    "finbit-google-cloud-storage-migration",
}


def final_jobs(alias: str, existing: dict[str, list[str]]) -> dict[str, list[str]]:
    return {
        task: (
            [
                f"enterprise-calibrated-v2-{alias}-{task}-a{attempt:02d}"
                for attempt in range(1, 9)
            ]
            if task in RECALIBRATED_TASKS
            else jobs
        )
        for task, jobs in existing.items()
    }


GROK_JOBS = {
    task: [
        f"enterprise-exact-frontier-r1-grok45-{task}-a{attempt:02d}"
        for attempt in range(1, 9)
    ]
    for task in OPUS_A01
}
SOL_JOBS = {
    task: [
        f"enterprise-exact-frontier-r1-gpt56sol-{task}-a{attempt:02d}"
        for attempt in range(1, 9)
    ]
    for task in OPUS_A01
}
MODEL_SPECS = {
    "opus5": {
        "model": "Claude Opus 5",
        "route": "amazon-bedrock/global.anthropic.claude-opus-5",
        "jobs": final_jobs("opus5-bedrock", OPUS_JOBS),
    },
    "grok45": {
        "model": "Grok 4.5",
        "route": "openrouter/x-ai/grok-4.5",
        "jobs": final_jobs("grok45", GROK_JOBS),
    },
    "gpt56sol": {
        "model": "GPT-5.6 Sol",
        "route": "openrouter/openai/gpt-5.6-sol",
        "jobs": final_jobs("gpt56sol", SOL_JOBS),
    },
}


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def redact_text(value: str) -> str:
    redacted = SENSITIVE_ASSIGNMENT.sub(r"\1<REDACTED>", value)
    for pattern in SENSITIVE_TOKEN_PATTERNS:
        redacted = pattern.sub("<REDACTED>", redacted)
    return redacted


def redact_artifact(value: object) -> object:
    if isinstance(value, dict):
        return {key: redact_artifact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact_artifact(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def trial_dir_for_result(job_dir: Path, result: dict) -> Path:
    for result_path in sorted(job_dir.glob("*/result.json")):
        try:
            candidate = json.loads(result_path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if candidate == result:
            return result_path.parent
    raise ValueError(f"could not locate selected result under {job_dir}")


def package_artifacts(
    alias: str,
    task: str,
    job: str,
    trial_dir: Path,
    result: dict,
    trajectory: dict,
    verifier: dict,
) -> dict:
    match = re.search(r"-a(\d+)$", job)
    if match is None:
        raise ValueError(f"job lacks attempt suffix: {job}")
    destination = PACKAGED / alias / task / f"attempt-{int(match.group(1)):02d}"
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    artifacts = {
        "trajectory": (destination / "trajectory.json", trajectory),
        "result": (destination / "result.json", result),
        "verifier_output": (destination / "verifier-output.json", verifier),
    }
    packaged = {}
    for label, (path, artifact) in artifacts.items():
        path.write_text(json.dumps(redact_artifact(artifact), indent=2) + "\n")
        packaged[label] = str(path.relative_to(ROOT / "sample-run"))
    verifier_stdout = trial_dir / "verifier" / "stdout.txt"
    if verifier_stdout.is_file():
        stdout_path = destination / "verifier-stdout.txt"
        stdout_path.write_text(redact_text(verifier_stdout.read_text()))
        packaged["verifier_stdout"] = str(stdout_path.relative_to(ROOT / "sample-run"))
    packaged["artifact_redaction"] = (
        "credential assignments, provider tokens, bearer tokens, and private keys redacted"
    )
    return packaged


def collect_attempt(alias: str, task: str, job: str, route: str) -> dict:
    job_dir = RAW / job
    checksum = directory_sha256(ROOT / "tasks" / task)
    result = complete_existing(
        job_dir,
        task,
        route=route,
        snapshot=TASK_SNAPSHOTS[task],
        agent_version=AGENT_VERSION,
        checksum=checksum,
        disable_task_tool=True,
    )
    if result is None:
        raise ValueError(f"missing final-checksum result: {job}")
    trial_dir = trial_dir_for_result(job_dir, result)
    completion_status = verifier_completion_status(trial_dir, task, result)
    if completion_status is None:
        raise ValueError(f"unscoreable verifier output: {job}")
    trajectory = json.loads((trial_dir / "agent" / "trajectory.json").read_text())
    verifier = json.loads((trial_dir / "verifier" / "output.json").read_text())
    # A candidate-caused suite-load failure is a scoreable zero even when the
    # verifier could not emit assertion rows.  Treat the absent list as empty
    # so the packaged evidence records every required assertion as failed.
    tests = verifier.get("tests") or []
    config = json.loads((ROOT / "tasks" / task / "tests" / "config.json").read_text())
    required = config["fail_to_pass"] + config["pass_to_pass"]
    verdicts = {item["name"]: item["status"] for item in tests}
    agent_result = result["agent_result"]
    reward = result["verifier_result"]["rewards"]["reward"]
    started = parse_timestamp(result["started_at"])
    finished = parse_timestamp(result["finished_at"])
    steps = trajectory["steps"]
    failed = [name for name in required if verdicts.get(name) != "passed"]
    auxiliary_failed = [
        item["name"]
        for item in tests
        if item["name"] not in required and item["status"] != "passed"
    ]
    packaged = package_artifacts(
        alias, task, job, trial_dir, result, trajectory, verifier
    )
    return {
        "model_alias": alias,
        "model_route": route,
        "task": task,
        "job": job,
        "task_sha256": checksum,
        "reward": reward,
        "passed_tests": sum(verdicts.get(name) == "passed" for name in required),
        "total_tests": len(required),
        "failed_tests": failed,
        "auxiliary_failed_tests": auxiliary_failed,
        "model_turns": sum(step.get("source") == "agent" for step in steps),
        "tool_calls": sum(len(step.get("tool_calls") or []) for step in steps),
        "wall_time_seconds": round((finished - started).total_seconds(), 3),
        "cost_usd": float(agent_result.get("cost_usd") or 0),
        "input_tokens": agent_result.get("n_input_tokens"),
        "cache_tokens": agent_result.get("n_cache_tokens"),
        "output_tokens": agent_result.get("n_output_tokens"),
        "grading_provenance": f"final task checksum; {completion_status}",
        **packaged,
    }


def main() -> int:
    model_results = []
    by_alias = {}
    all_attempts = []
    for alias, spec in MODEL_SPECS.items():
        attempts = [
            collect_attempt(alias, task, job, spec["route"])
            for task, jobs in spec["jobs"].items()
            for job in jobs
        ]
        all_attempts.extend(attempts)
        task_results = []
        for task in spec["jobs"]:
            task_attempts = [item for item in attempts if item["task"] == task]
            solves = sum(item["reward"] == 1 for item in task_attempts)
            task_results.append(
                {
                    "task": task,
                    "solves": solves,
                    "attempts": len(task_attempts),
                    "pass_at_1": round(solves / len(task_attempts), 6),
                    "results": task_attempts,
                }
            )
        model_result = {
            "model": spec["model"],
            "alias": alias,
            "route": spec["route"],
            "status": "eight-attempt-stage-complete",
            "solves": sum(item["reward"] == 1 for item in attempts),
            "attempts": len(attempts),
            "macro_pass_at_1": round(
                sum(item["pass_at_1"] for item in task_results)
                / len(task_results),
                6,
            ),
            "cost_usd": round(sum(item["cost_usd"] for item in attempts), 6),
            "task_results": task_results,
        }
        model_results.append(model_result)
        by_alias[alias] = {
            item["task"]: item for item in model_result["task_results"]
        }

    gate_tasks = []
    for task in OPUS_A01:
        grok_solves = by_alias["grok45"][task]["solves"]
        opus_solves = by_alias["opus5"][task]["solves"]
        if 1 <= grok_solves <= 6:
            qualifies = True
            reason = "Grok 4.5 solved between one and six of eight rollouts."
        elif grok_solves == 0 and opus_solves > 0:
            qualifies = True
            reason = (
                "Grok 4.5 solved zero of eight, but comparable Claude Opus 5 "
                "completed the task."
            )
        elif grok_solves == 0:
            qualifies = False
            reason = (
                "Neither Grok 4.5 nor Claude Opus 5 completed the task in eight "
                "rollouts, so learnability is not demonstrated."
            )
        else:
            qualifies = False
            reason = "Grok 4.5 solved seven or eight rollouts, above the XAI range."
        gate_tasks.append(
            {
                "task": task,
                "grok45_solves": grok_solves,
                "opus5_solves": opus_solves,
                "gpt56sol_solves": by_alias["gpt56sol"][task]["solves"],
                "qualifies": qualifies,
                "reason": reason,
            }
        )

    selected_cost = round(sum(item["cost_usd"] for item in all_attempts), 6)
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "acceptance_policy": (
            "Only scoreable trials matching the final task checksum, exact model route, "
            "OpenCode version, Daytona snapshot, and denied task tool are counted. "
            "Scoreable means complete verifier output or an explicit candidate-caused "
            "test-suite load failure scored as zero; transport and silent partial-output "
            "failures are excluded."
        ),
        "xai_gate": {
            "rollouts_per_task_model": 8,
            "rule": (
                "Grok 4.5 must solve one to six of eight rollouts. Zero of eight "
                "qualifies only when a comparable model, Claude Opus 5, completes "
                "the task."
            ),
            "qualifying_tasks": sum(item["qualifies"] for item in gate_tasks),
            "total_tasks": len(gate_tasks),
            "tasks": gate_tasks,
        },
        "budget_accounting": {
            "selected_trial_cost_usd": selected_cost,
            "recorded_spend_usd": round(recorded_spend(LEDGER), 6),
            "target_budget_usd": 2000,
            "hard_budget_usd": 3000,
            "note": (
                "Recorded spend is conservative and includes exploratory and "
                "superseded-checksum trials excluded from the score denominator."
            ),
        },
        "models": model_results,
    }
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n")
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                "models": {
                    item["alias"]: f"{item['solves']}/{item['attempts']}"
                    for item in model_results
                },
                "xai_gate": f"{output['xai_gate']['qualifying_tasks']}/8",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
