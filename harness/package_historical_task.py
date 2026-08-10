#!/usr/bin/env python3
"""Materialize historical oracle and verifier patches from a private Git export.

The public task manifest stores only immutable commit IDs and path filters. The
source repository stays outside this repository; generated task artifacts are
reviewable before they are committed or published.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "authoring" / "historical_tasks.json"


def git(git_dir: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", f"--git-dir={git_dir}", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def filtered_diff(
    git_dir: Path,
    base: str,
    target: str,
    includes: list[str],
    excludes: list[str],
) -> str:
    pathspecs = [*includes, *(f":(exclude){item}" for item in excludes)]
    return git(
        git_dir,
        "diff",
        "--binary",
        "--full-index",
        "--no-ext-diff",
        base,
        target,
        "--",
        *pathspecs,
    )


def oracle_diff(
    git_dir: Path,
    base: str,
    target: str,
    includes: list[str],
    excludes: list[str],
    post_patch: Path | None,
) -> str:
    if post_patch is None:
        return filtered_diff(git_dir, base, target, includes, excludes)
    with tempfile.TemporaryDirectory(prefix="historical-oracle-") as raw_dir:
        checkout = Path(raw_dir) / "repo"
        subprocess.run(
            ["git", "clone", "--shared", "--quiet", str(git_dir), str(checkout)],
            check=True,
        )
        subprocess.run(
            ["git", "checkout", "--detach", "--quiet", target],
            cwd=checkout,
            check=True,
        )
        subprocess.run(
            ["git", "apply", str(post_patch)],
            cwd=checkout,
            check=True,
        )
        pathspecs = [*includes, *(f":(exclude){item}" for item in excludes)]
        completed = subprocess.run(
            [
                "git",
                "diff",
                "--binary",
                "--full-index",
                "--no-ext-diff",
                base,
                "--",
                *pathspecs,
            ],
            cwd=checkout,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout


def added_content_patch(content: str, target: str) -> str:
    if not content.endswith("\n"):
        content += "\n"
    data = content.encode()
    digest = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
    lines = content.splitlines()
    body = "\n".join(f"+{line}" for line in lines) + "\n"
    return (
        f"diff --git a/{target} b/{target}\n"
        "new file mode 100644\n"
        f"index {'0' * 40}..{digest}\n"
        "--- /dev/null\n"
        f"+++ b/{target}\n"
        f"@@ -0,0 +1,{len(lines)} @@\n"
        f"{body}"
    )


def added_file_patch(source: Path, target: str) -> str:
    return added_content_patch(source.read_text(), target)


def select_added_file_patches(patch: str, targets: set[str]) -> str:
    """Retain reviewed generated-file sections without reopening source Git."""
    sections = re.split(r"(?=^diff --git )", patch, flags=re.MULTILINE)
    selected: dict[str, str] = {}
    for section in sections:
        match = re.match(r"diff --git a/(.+) b/(.+)\n", section)
        if match and match.group(1) == match.group(2) and match.group(2) in targets:
            selected[match.group(2)] = section
    missing = targets - selected.keys()
    if missing:
        raise ValueError(f"existing test patch is missing generated files: {sorted(missing)}")
    return "".join(selected[target] for target in sorted(targets))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    parser.add_argument("--git-dir", type=Path)
    parser.add_argument(
        "--local-tests-only",
        action="store_true",
        help="regenerate local extra test files while preserving the existing oracle",
    )
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text())
    if args.task not in manifest:
        parser.error(f"unknown historical task: {args.task}")
    spec = manifest[args.task]
    task_dir = ROOT / "tasks" / args.task
    template_path = task_dir / "tests" / "config.template.json"
    if not template_path.is_file():
        parser.error(f"missing verifier template: {template_path}")

    base = spec["base_commit"]
    target = spec["target_commit"]
    tests = ""
    if args.local_tests_only:
        if spec["test_paths"]:
            parser.error("--local-tests-only cannot preserve historical test-path edits")
        existing = json.loads((task_dir / "tests" / "config.json").read_text())
        oracle = existing.get("patch", "")
        git_targets = {
            item["target"] for item in spec.get("extra_git_test_files", [])
        }
        try:
            tests = select_added_file_patches(
                existing.get("test_patch", ""), git_targets
            )
        except ValueError as exc:
            parser.error(str(exc))
        # Metadata such as required test names and selected test files remains
        # author-controlled in the reviewed template. Local regeneration must
        # not silently retain stale selections from an older generated config.
        config = json.loads(template_path.read_text())
    else:
        if args.git_dir is None:
            parser.error("--git-dir is required unless --local-tests-only is used")
        git_dir = args.git_dir.expanduser().resolve()
        for commit in (base, target):
            git(git_dir, "cat-file", "-e", f"{commit}^{{commit}}")

        post_patch = spec.get("oracle_post_patch")
        oracle = oracle_diff(
            git_dir,
            base,
            target,
            spec["oracle_paths"],
            spec.get("oracle_excludes", []),
            ROOT / post_patch if post_patch else None,
        )
        if spec["test_paths"]:
            tests = filtered_diff(
                git_dir,
                base,
                target,
                spec["test_paths"],
                spec.get("test_excludes", []),
            )
        config = json.loads(template_path.read_text())
    for extra in spec.get("extra_test_files", []):
        source = ROOT / extra["source"]
        if not source.is_file():
            parser.error(f"missing extra gold test: {source}")
        tests += added_file_patch(source, extra["target"])
    if not args.local_tests_only:
        for extra in spec.get("extra_git_test_files", []):
            content = git(git_dir, "show", f"{target}:{extra['source']}")
            tests += added_content_patch(content, extra["target"])
    if not oracle.strip():
        parser.error("oracle diff is empty")
    if not tests.strip():
        parser.error("test diff is empty")

    config["base_commit"] = base
    config["patch"] = oracle
    config["test_patch"] = tests

    (task_dir / "solution" / "oracle.patch").write_text(oracle)
    (task_dir / "tests" / "config.json").write_text(
        json.dumps(config, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                "task": args.task,
                "base_commit": base,
                "target_commit": target,
                "oracle_bytes": len(oracle.encode()),
                "test_patch_bytes": len(tests.encode()),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
