#!/usr/bin/env python3
"""Build a sealed Daytona snapshot for a pinned historical Node task."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from pathlib import Path

from daytona import CreateSnapshotParams, Daytona, Image, Resources


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "authoring" / "historical_tasks.json"


def load_env(path: Path) -> None:
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key] = value.strip().strip('"').strip("'")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--env-file", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    if args.task not in manifest:
        parser.error(f"unknown historical task: {args.task}")
    spec = manifest[args.task]
    repo = args.repo.expanduser().resolve()
    env_file = args.env_file.expanduser().resolve()
    if not (repo / "package.json").is_file():
        parser.error(f"not a Node repository: {repo}")
    if not env_file.is_file():
        parser.error(f"env file does not exist: {env_file}")

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if commit != spec["base_commit"]:
        parser.error(
            f"checkout must be pinned to {spec['base_commit']}; found {commit}"
        )

    snapshot_name = f"harbor-probe-{args.task}-8g"
    load_env(env_file)
    client = Daytona()
    existing = [
        item
        for item in client.snapshot.list(limit=200).items
        if item.name == snapshot_name
    ]
    if existing:
        parser.error(
            f"snapshot already exists: {snapshot_name} ({existing[0].state})"
        )

    preinstall = spec.get("preinstall_packages", [])
    preinstall_commands = []
    for item in preinstall:
        if item.get("method") == "npm-install":
            preinstall_commands.append(
                "npm install --ignore-scripts --no-save --package-lock=false "
                + shlex.quote(item["spec"])
            )
        else:
            preinstall_commands.append(
                "archive=$(npm pack --silent {package}) && "
                "mkdir -p node_modules/{module} && "
                "tar -xzf \"$archive\" -C node_modules/{module} --strip-components=1 && "
                "rm -f \"$archive\"".format(
                    package=shlex.quote(item["spec"]),
                    module=shlex.quote(item["module"]),
                )
            )
    preinstall_command = " && ".join(preinstall_commands) if preinstall_commands else "true"
    image = (
        Image.base("node:20-bookworm")
        .run_commands(
            "apt-get update && apt-get install -y --no-install-recommends "
            "git python3 curl && rm -rf /var/lib/apt/lists/*"
        )
        .add_local_dir(repo, "/app")
        .workdir("/app")
        .run_commands(
            "find . -type f -not -path './.git/*' "
            "\\( -name '.env' -o -name '.env.*' -o -name '*.pem' -o -name '*.key' "
            "\\) -delete",
            "rm -rf .git node_modules dist",
            "npm ci --ignore-scripts",
            preinstall_command,
            "npm run build",
            "git init -qb main && git config user.email evaluator@example.invalid && "
            "git config user.name evaluator && git add -A && "
            "git commit -qm 'import task base'",
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
