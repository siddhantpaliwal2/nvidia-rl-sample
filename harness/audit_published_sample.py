#!/usr/bin/env python3
"""Audit the public NVIDIA sample's result matrix and packaged evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path

from run_frontier_daytona import directory_sha256
from task_paths import task_directory


ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "sample-run" / "results.json"
CONTROLS = ROOT / "sample-run" / "controls.json"
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
EXPECTED_ROUTES = {
    "nemotron3-ultra": "openrouter/nvidia/nemotron-3-ultra-550b-a55b",
    "opus5": "amazon-bedrock/global.anthropic.claude-opus-5",
    "gpt56sol-historical": "openrouter/openai/gpt-5.6-sol",
}
SECRET_PATTERNS = {
    "openrouter-key": re.compile(rb"sk-or-v1-[A-Za-z0-9_-]{20,}"),
    "aws-access-key": re.compile(rb"(?:AKIA|ASIA)[0-9A-Z]{16}"),
    "google-api-key": re.compile(rb"AIza[0-9A-Za-z_-]{30,}"),
    "github-token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}


def main() -> int:
    errors: list[str] = []
    results = json.loads(RESULTS.read_text())
    controls = json.loads(CONTROLS.read_text())
    models = {item["alias"]: item for item in results["models"]}
    current = {task: directory_sha256(task_directory(ROOT, task)) for task in TASKS}

    if set(models) != set(EXPECTED_ROUTES):
        errors.append(f"unexpected model aliases: {sorted(models)}")
    control_tasks = {item["task"]: item for item in controls["tasks"]}
    if set(control_tasks) != set(TASKS):
        errors.append("controls do not cover exactly the published task cohort")

    for task in TASKS:
        if control_tasks.get(task, {}).get("task_sha256") != current[task]:
            errors.append(f"control checksum mismatch: {task}")

    artifact_count = 0
    for alias, route in EXPECTED_ROUTES.items():
        model = models.get(alias)
        if model is None:
            continue
        if model.get("route") != route:
            errors.append(f"route mismatch: {alias}")
        if model.get("attempts") != 32:
            errors.append(f"{alias} does not have 32 packaged attempts")
        task_rows = {item["task"]: item for item in model.get("task_results", [])}
        if set(task_rows) != set(TASKS):
            errors.append(f"task coverage mismatch: {alias}")
            continue
        for task in TASKS:
            rows = task_rows[task].get("results", [])
            if len(rows) != 4:
                errors.append(f"{alias}/{task} does not have four attempts")
            for expected_attempt, row in enumerate(rows, start=1):
                if row.get("attempt") != expected_attempt:
                    errors.append(f"attempt numbering mismatch: {alias}/{task}")
                if row.get("route") != route:
                    errors.append(f"trial route mismatch: {alias}/{task}")
                relation = row.get("checksum_relation")
                expected_relation = (
                    "historical" if alias == "gpt56sol-historical" else "exact-current"
                )
                if relation != expected_relation:
                    errors.append(f"checksum relation mismatch: {alias}/{task}")
                if alias != "gpt56sol-historical" and row.get(
                    "task_sha256"
                ) != current[task]:
                    errors.append(f"current checksum mismatch: {alias}/{task}")
                if row.get("passed_required_tests", 0) + len(
                    row.get("failed_required_tests", [])
                ) != row.get("total_required_tests"):
                    errors.append(f"incomplete required verdicts: {alias}/{task}")
                provenance = row.get("grading_provenance")
                if provenance not in {
                    "complete_verifier_output",
                    "candidate_suite_failed_before_assertions",
                    "candidate_verifier_abort",
                }:
                    errors.append(f"invalid grading provenance: {alias}/{task}")
                if provenance in {
                    "candidate_suite_failed_before_assertions",
                    "candidate_verifier_abort",
                } and row.get("reward") != 0:
                    errors.append(f"verifier abort is not scored zero: {alias}/{task}")
                for label, relative in row.get("artifacts", {}).items():
                    if label == "redaction":
                        continue
                    artifact = ROOT / relative
                    if not artifact.is_file():
                        errors.append(f"missing artifact: {relative}")
                        continue
                    artifact_count += 1
                    if artifact.suffix == ".json":
                        try:
                            json.loads(artifact.read_text())
                        except json.JSONDecodeError:
                            errors.append(f"invalid JSON: {relative}")

    secret_findings = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        data = path.read_bytes()
        for kind, pattern in SECRET_PATTERNS.items():
            if pattern.search(data):
                secret_findings.append({"path": str(path.relative_to(ROOT)), "kind": kind})
    if secret_findings:
        errors.append("secret-pattern findings exist")

    output = {
        "passed": not errors,
        "tasks": len(TASKS),
        "models": sorted(models),
        "nemotron_trials": models.get("nemotron3-ultra", {}).get("attempts"),
        "packaged_artifacts": artifact_count,
        "secret_findings": secret_findings,
        "errors": errors,
    }
    print(json.dumps(output, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
