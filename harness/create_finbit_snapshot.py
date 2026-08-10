#!/usr/bin/env python3
"""Build a sealed Daytona snapshot from a pre-sanitized Finbit task export."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

from daytona import CreateSnapshotParams, Daytona, Image, Resources


COMMON_FORBIDDEN_PATHS = (
    "test",
    "web-app/testData",
    "grails-app/conf/google-service-account.json",
)
SECRET_PATTERNS = (
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb'"type"\s*:\s*"service_account"'),
)
TASK_PROFILES = {
    "bank-parser-consolidation": {
        "snapshot": "harbor-probe-finbit-bank-parser-consolidation-8g",
        "required": (
            "src/groovy/com/bankScraper/bank/BankTransactionUtil.groovy",
            "grails-app/services/com/bankScraper/bank/pdf/BankOfBarodaPdfService.groovy",
            "lib/pdf2table-1.0.jar",
        ),
        "allowed": None,
    },
    "google-cloud-storage-migration": {
        "snapshot": "harbor-probe-finbit-google-cloud-storage-migration-8g",
        "required": (
            "application.properties",
            "grails-app/conf/BuildConfig.groovy",
            "grails-app/domain/com/bankScraper/bank/Document.groovy",
            "src/groovy/com/bankScraper/Enums.groovy",
            "src/groovy/com/bankScraper/HelperMethod.groovy",
            "lib/tika-app-1.14.jar",
        ),
        "allowed": (
            "application.properties",
            "grails-app/conf/BuildConfig.groovy",
            "grails-app/domain/com/bankScraper/bank/Document.groovy",
            "src/groovy/com/bankScraper/Enums.groovy",
            "src/groovy/com/bankScraper/HelperMethod.groovy",
            "lib/",
        ),
    },
}


def load_env(path: Path) -> None:
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key] = value.strip().strip('"').strip("'")


def audit(repo: Path, profile_name: str) -> None:
    profile = TASK_PROFILES[profile_name]
    required = profile["required"]
    missing = [path for path in required if not (repo / path).is_file()]
    if missing:
        raise ValueError(f"sanitized export is missing required paths: {missing}")
    present = [path for path in COMMON_FORBIDDEN_PATHS if (repo / path).exists()]
    if present:
        raise ValueError(f"refusing unsanitized Finbit export; forbidden paths: {present}")
    allowed = profile["allowed"]
    for path in repo.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = path.relative_to(repo).as_posix()
        if allowed and not any(
            relative == item or (item.endswith("/") and relative.startswith(item))
            for item in allowed
        ):
            raise ValueError(f"unexpected path in restricted export: {relative}")
        if path.stat().st_size > 5_000_000:
            continue
        data = path.read_bytes()
        if any(pattern.search(data) for pattern in SECRET_PATTERNS):
            raise ValueError(f"possible credential in sanitized export: {path.relative_to(repo)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--profile", choices=tuple(TASK_PROFILES), required=True)
    args = parser.parse_args()

    repo = args.repo.expanduser().resolve()
    env_file = args.env_file.expanduser().resolve()
    if not repo.is_dir():
        parser.error(f"repository directory does not exist: {repo}")
    if not env_file.is_file():
        parser.error(f"env file does not exist: {env_file}")
    try:
        audit(repo, args.profile)
    except ValueError as error:
        parser.error(str(error))

    snapshot_name = TASK_PROFILES[args.profile]["snapshot"]
    load_env(env_file)
    client = Daytona()
    existing = [
        item
        for item in client.snapshot.list(limit=200).items
        if item.name == snapshot_name
    ]
    if existing:
        parser.error(f"snapshot already exists: {snapshot_name} ({existing[0].state})")

    image = (
        Image.base("eclipse-temurin:8-jdk")
        .run_commands(
            "apt-get update && apt-get install -y --no-install-recommends "
            "curl git python3 unzip && rm -rf /var/lib/apt/lists/*",
            "curl -L --fail --retry 3 -o /tmp/grails.zip "
            "https://github.com/apache/grails-core/releases/download/v2.3.11/grails-2.3.11.zip "
            "&& unzip -q /tmp/grails.zip -d /opt && rm -f /tmp/grails.zip",
        )
        .env({"GRAILS_HOME": "/opt/grails-2.3.11", "JAVA_HOME": "/opt/java/openjdk"})
        .add_local_dir(repo, "/app")
        .workdir("/app")
        .run_commands(
            "rm -rf .git",
            "git init -qb main && git config user.email evaluator@example.invalid && "
            "git config user.name evaluator && git add -A && "
            "git commit -qm 'import sanitized task base'",
            "mkdir -p /logs/verifier",
        )
    )
    snapshot = client.snapshot.create(
        CreateSnapshotParams(
            name=snapshot_name,
            image=image,
            resources=Resources(cpu=2, memory=8, disk=10),
        ),
        on_logs=lambda chunk: print(chunk, flush=True),
        timeout=0,
    )
    print(f"snapshot={snapshot.name} state={snapshot.state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
