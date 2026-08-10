#!/usr/bin/env python3
"""Audit historical task boundaries, generated patches, controls, and secrets."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "authoring" / "historical_tasks.json"
CONTROL_SUMMARY = ROOT / "sample-run" / "enterprise-controls-summary.json"
CONTROL_JOBS = {
    "paigo-dimension-pricing-tiers": (
        "eng830-null-daytona-r10",
        "eng830-oracle-daytona-r10",
    ),
    "paigo-top-up-billing-lifecycle": (
        "eng1167-null-daytona-r6",
        "eng1167-oracle-daytona-r6",
    ),
    "paigo-s3-datastore-measurement": (
        "eng411-null-daytona-r5",
        "eng411-oracle-daytona-r5",
    ),
    "paigo-customer-identity-migration": (
        "eng504a-null-daytona-r3",
        "eng504a-oracle-daytona-r3",
    ),
    "paigo-customer-billing-schedule-migration": (
        "eng504b-null-daytona-r6",
        "eng504b-oracle-daytona-r6",
    ),
    "champ-email-inbox-infrastructure": (
        "champ2197-null-daytona-r10",
        "champ2197-oracle-daytona-r10",
    ),
    "finbit-bank-parser-consolidation": (
        "finbit-parser-null-daytona-r2",
        "finbit-parser-oracle-daytona-r2",
    ),
    "finbit-google-cloud-storage-migration": (
        "finbit-cloud-null-daytona-r3",
        "finbit-cloud-oracle-daytona-r3",
    ),
}
SECRET_PATTERNS = {
    "aws-access-key": re.compile(rb"(?:AKIA|ASIA)[0-9A-Z]{16}"),
    "google-api-key": re.compile(rb"AIza[0-9A-Za-z_-]{30,}"),
    "private-key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "service-account": re.compile(rb'"type"\s*:\s*"service_account"'),
    "azure-account-key": re.compile(rb"AccountKey=[A-Za-z0-9+/=]{20,}"),
    "github-token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    "openrouter-key": re.compile(rb"sk-or-v1-[A-Za-z0-9]{20,}"),
}
FORBIDDEN_BASENAMES = {
    ".env",
    "google-service-account.json",
}
IMPLEMENTATION_INSPECTION_PATTERNS = {
    "source-file-read": re.compile(
        rb"(?:readFileSync|fs\.readFile|read_text\(|Files\.readString)"
    ),
    "git-inspection": re.compile(rb"(?:git\s+(?:diff|show|log)|child_process|subprocess)"),
    "oracle-access": re.compile(rb"(?:oracle\.patch|/solution(?:/|\b))"),
}


def patch_paths(patch: str) -> list[str]:
    return re.findall(r"^diff --git a/(.+?) b/", patch, flags=re.MULTILINE)


def modified_patch_paths(patch: str) -> list[str]:
    modified = []
    current = None
    for line in patch.splitlines():
        if line.startswith("diff --git a/"):
            current = line.split(" b/", 1)[0].removeprefix("diff --git a/")
        elif current is not None and line.startswith("--- "):
            if line != "--- /dev/null":
                modified.append(current)
            current = None
    return modified


def path_allowed(path: str, specs: list[str]) -> bool:
    for spec in specs:
        plain = spec.rstrip("/")
        if path == plain or path.startswith(f"{plain}/"):
            return True
    return False


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


def control_mean(path: Path) -> tuple[float, int]:
    result = json.loads(path.read_text())
    evals = result.get("stats", {}).get("evals", {})
    if len(evals) != 1:
        raise ValueError(f"expected one evaluator in {path}")
    stats = next(iter(evals.values()))
    return float(stats["metrics"][0]["mean"]), int(stats["n_errors"])


def control_verdicts(job_dir: Path) -> dict[str, str]:
    outputs = sorted(job_dir.glob("*/verifier/output.json"))
    if len(outputs) != 1:
        raise ValueError(f"expected one verifier output in {job_dir}")
    output = json.loads(outputs[0].read_text())
    return {item["name"]: item["status"] for item in output.get("tests", [])}


def audit_task(task: str, spec: dict, controls_dir: Path, summary: dict) -> dict:
    task_dir = ROOT / "tasks" / task
    config_path = task_dir / "tests" / "config.json"
    config = json.loads(config_path.read_text())
    template = json.loads((task_dir / "tests" / "config.template.json").read_text())
    errors = []

    for key in (
        "instance_id",
        "repo",
        "fail_to_pass",
        "pass_to_pass",
        "selected_test_files_to_run",
    ):
        if config.get(key) != template.get(key):
            errors.append(f"generated config differs from template for {key}")

    instruction_copy = ROOT / "instructions" / f"{task}.md"
    if not instruction_copy.is_file():
        errors.append("missing readable instruction copy")
    elif instruction_copy.read_bytes() != (task_dir / "instruction.md").read_bytes():
        errors.append("readable instruction copy differs from canonical task prompt")

    if config.get("base_commit") != spec["base_commit"]:
        errors.append("base commit differs from manifest")
    if not config.get("fail_to_pass") or not config.get("pass_to_pass"):
        errors.append("both fail-to-pass and pass-to-pass sets are required")

    for extra in spec.get("extra_test_files", []):
        test_source = ROOT / extra["source"]
        data = test_source.read_bytes()
        for kind, pattern in IMPLEMENTATION_INSPECTION_PATTERNS.items():
            if pattern.search(data):
                errors.append(f"hidden test uses {kind}: {extra['source']}")

    unexpected_oracle = [
        path
        for path in patch_paths(config.get("patch", ""))
        if not path_allowed(path, spec["oracle_paths"])
    ]
    if unexpected_oracle:
        errors.append(f"oracle escapes allowlist: {unexpected_oracle}")

    allowed_tests = [
        *spec["test_paths"],
        *(item["target"] for item in spec.get("extra_test_files", [])),
        *(item["target"] for item in spec.get("extra_git_test_files", [])),
    ]
    unexpected_tests = [
        path
        for path in patch_paths(config.get("test_patch", ""))
        if not path_allowed(path, allowed_tests)
    ]
    if unexpected_tests:
        errors.append(f"test patch escapes allowlist: {unexpected_tests}")
    modified_tests = modified_patch_paths(config.get("test_patch", ""))
    if modified_tests:
        errors.append(
            "hidden test patch must add isolated files, not edit candidate files: "
            f"{modified_tests}"
        )
    collision_prone_tests = [
        path
        for path in patch_paths(config.get("test_patch", ""))
        if not (path.startswith("xai-tests/") or path.endswith(".gold.spec.ts"))
    ]
    if collision_prone_tests:
        errors.append(
            "hidden test paths must use a reserved gold-test namespace: "
            f"{collision_prone_tests}"
        )

    null_job, oracle_job = CONTROL_JOBS[task]
    summary_entry = next(
        (item for item in summary.get("tasks", []) if item.get("task") == task),
        None,
    )
    checksum = directory_sha256(task_dir)
    if summary_entry is None:
        errors.append("missing controls-summary entry")
    else:
        if summary_entry.get("task_sha256") != checksum:
            errors.append("controls-summary checksum differs from current task")
        if (summary_entry.get("null_job"), summary_entry.get("oracle_job")) != (
            null_job,
            oracle_job,
        ):
            errors.append("controls-summary job selection differs from audit")
    null_mean, null_errors = control_mean(controls_dir / null_job / "result.json")
    oracle_mean, oracle_errors = control_mean(
        controls_dir / oracle_job / "result.json"
    )
    null_verdicts = control_verdicts(controls_dir / null_job)
    oracle_verdicts = control_verdicts(controls_dir / oracle_job)
    if (null_mean, null_errors) != (0.0, 0):
        errors.append(f"null control is mean={null_mean}, errors={null_errors}")
    if (oracle_mean, oracle_errors) != (1.0, 0):
        errors.append(
            f"oracle control is mean={oracle_mean}, errors={oracle_errors}"
        )
    null_unexpected = [
        name for name in config["fail_to_pass"] if null_verdicts.get(name) == "passed"
    ]
    null_regressions = [
        name for name in config["pass_to_pass"] if null_verdicts.get(name) != "passed"
    ]
    oracle_missing = [
        name
        for name in config["fail_to_pass"] + config["pass_to_pass"]
        if oracle_verdicts.get(name) != "passed"
    ]
    ungated_oracle_repairs = [
        name
        for name, status in null_verdicts.items()
        if status != "passed"
        and oracle_verdicts.get(name) == "passed"
        and name not in config["fail_to_pass"]
    ]
    if null_unexpected:
        errors.append(f"null unexpectedly passes fail-to-pass tests: {null_unexpected}")
    if null_regressions:
        errors.append(f"null does not preserve pass-to-pass tests: {null_regressions}")
    if oracle_missing:
        errors.append(f"oracle lacks passing required tests: {oracle_missing}")
    if ungated_oracle_repairs:
        errors.append(
            "null-fail/oracle-pass behavior is not reward-gated: "
            f"{ungated_oracle_repairs}"
        )

    return {
        "task": task,
        "task_sha256": checksum,
        "f2p": len(config["fail_to_pass"]),
        "p2p": len(config["pass_to_pass"]),
        "oracle_files": len(patch_paths(config["patch"])),
        "oracle_bytes": len(config["patch"].encode()),
        "null": null_mean,
        "oracle": oracle_mean,
        "errors": errors,
    }


def secret_findings(task_names: list[str]) -> list[dict]:
    roots = [
        ROOT / "authoring",
        ROOT / "gold-tests",
        ROOT / "harness",
        ROOT / "sample-run" / "enterprise-controls-summary.json",
        ROOT / "sample-run" / "enterprise-champ-fairness-checkpoint.json",
        ROOT / "sample-run" / "enterprise-model-results.json",
        ROOT / "sample-run" / "enterprise-trials",
        *(ROOT / "tasks" / task for task in task_names),
    ]
    findings = []
    seen = set()
    for root in roots:
        if not root.exists():
            continue
        candidates = [root] if root.is_file() else root.rglob("*")
        for path in candidates:
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            relative = path.relative_to(ROOT).as_posix()
            if path.name in FORBIDDEN_BASENAMES or path.suffix in {".pem", ".key"}:
                findings.append({"path": relative, "kind": "forbidden-filename"})
            data = path.read_bytes()
            for kind, pattern in SECRET_PATTERNS.items():
                if pattern.search(data):
                    findings.append({"path": relative, "kind": kind})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--controls-dir",
        type=Path,
        default=ROOT / "sample-run" / "enterprise-controls",
    )
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    summary = json.loads(CONTROL_SUMMARY.read_text())
    missing = sorted(set(CONTROL_JOBS) - set(manifest))
    extra = sorted(set(manifest) - set(CONTROL_JOBS))
    if missing or extra:
        raise SystemExit(f"manifest/control mismatch: missing={missing}, extra={extra}")

    reports = [
        audit_task(task, manifest[task], args.controls_dir, summary)
        for task in CONTROL_JOBS
    ]
    findings = secret_findings(list(CONTROL_JOBS))
    output = {
        "tasks": reports,
        "secret_findings": findings,
        "passed": not findings and all(not item["errors"] for item in reports),
    }
    print(json.dumps(output, indent=2))
    return 0 if output["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
