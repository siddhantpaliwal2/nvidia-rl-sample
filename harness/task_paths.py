"""Resolve frozen internal task IDs to neutral public task directories."""

from __future__ import annotations

from pathlib import Path


PUBLIC_TASK_NAMES = {
    "paigo-dimension-pricing-tiers": "dimension-pricing-tiers",
    "paigo-top-up-billing-lifecycle": "top-up-billing-lifecycle",
    "paigo-s3-datastore-measurement": "s3-datastore-measurement",
    "paigo-customer-identity-migration": "customer-identity-migration",
    "paigo-customer-billing-schedule-migration": "customer-billing-schedule-migration",
    "champ-email-inbox-infrastructure": "email-inbox-infrastructure",
    "finbit-bank-parser-consolidation": "bank-parser-consolidation",
    "finbit-google-cloud-storage-migration": "google-cloud-storage-migration",
}


def public_task_name(task: str) -> str:
    return PUBLIC_TASK_NAMES.get(task, task)


def task_directory(root: Path, task: str) -> Path:
    return root / "tasks" / public_task_name(task)
