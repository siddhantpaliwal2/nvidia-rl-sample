#!/usr/bin/env python3
"""Convert one or more Jest JSON reports into Harbor verifier verdicts."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    tests: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_path in sys.argv[1:]:
        path = Path(raw_path)
        if not path.is_file():
            continue
        try:
            report = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        for suite in report.get("testResults", []):
            for assertion in suite.get("assertionResults", []):
                name = assertion.get("fullName") or assertion.get("title")
                if not name or name in seen:
                    continue
                seen.add(name)
                status = "passed" if assertion.get("status") == "passed" else "failed"
                tests.append({"name": name, "status": status})
    print(json.dumps({"tests": tests}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
