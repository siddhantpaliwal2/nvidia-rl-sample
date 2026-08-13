#!/usr/bin/env python3
"""Verify that every task has a complete, task-scoped readable gold suite."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "tasks"
GOLD_TESTS = ROOT / "gold-tests"
ALLOWED_ROOT_FILES = {"README.md"}
PUBLIC_NAMES = {
    "paigo-dimension-pricing-tiers": "dimension-pricing-tiers",
    "paigo-top-up-billing-lifecycle": "top-up-billing-lifecycle",
    "paigo-s3-datastore-measurement": "s3-datastore-measurement",
    "paigo-customer-identity-migration": "customer-identity-migration",
    "paigo-customer-billing-schedule-migration": "customer-billing-schedule-migration",
    "champ-email-inbox-infrastructure": "email-inbox-infrastructure",
    "finbit-bank-parser-consolidation": "bank-parser-consolidation",
    "finbit-google-cloud-storage-migration": "google-cloud-storage-migration",
}


def added_file_bodies(patch: str) -> list[bytes]:
    """Return reconstructed contents for every file added by a test patch."""
    bodies: list[bytes] = []
    current: list[str] | None = None
    in_hunk = False

    for line in patch.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if current is not None:
                bodies.append("".join(current).encode())
            current = []
            in_hunk = False
        elif current is not None and line.startswith("@@ "):
            in_hunk = True
        elif in_hunk and line.startswith("+") and not line.startswith("+++"):
            current.append(line[1:])
        elif line.startswith("\\ No newline") and current:
            current[-1] = current[-1].removesuffix("\n")

    if current is not None:
        bodies.append("".join(current).encode())
    return bodies


def digest_counts(items: list[bytes]) -> Counter[str]:
    return Counter(hashlib.sha256(item).hexdigest() for item in items)


def main() -> int:
    errors: list[str] = []
    task_names = {path.name for path in TASKS.iterdir() if path.is_dir()}
    expected_dirs = {PUBLIC_NAMES.get(task, task) for task in task_names}
    gold_dirs = {path.name for path in GOLD_TESTS.iterdir() if path.is_dir()}
    root_files = {path.name for path in GOLD_TESTS.iterdir() if path.is_file()}

    if root_files != ALLOWED_ROOT_FILES:
        errors.append(
            "gold-tests root files differ from the README-only policy: "
            f"{sorted(root_files)}"
        )
    if gold_dirs != expected_dirs:
        errors.append(
            "gold-test folders differ from public task names: "
            f"missing={sorted(expected_dirs - gold_dirs)}, "
            f"extra={sorted(gold_dirs - expected_dirs)}"
        )

    reports = []
    for task in sorted(task_names):
        public_name = PUBLIC_NAMES.get(task, task)
        config = json.loads((TASKS / task / "tests" / "config.json").read_text())
        patch_files = added_file_bodies(config.get("test_patch", ""))
        readable_paths = sorted(
            path for path in (GOLD_TESTS / public_name).rglob("*") if path.is_file()
        )
        readable_files = [path.read_bytes() for path in readable_paths]
        complete = digest_counts(patch_files) == digest_counts(readable_files)
        if not complete:
            errors.append(f"readable suite differs from task test patch: {public_name}")
        reports.append(
            {
                "task": public_name,
                "injected_files": len(patch_files),
                "readable_files": len(readable_files),
                "complete": complete,
            }
        )

    output = {"passed": not errors, "tasks": reports, "errors": errors}
    print(json.dumps(output, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
