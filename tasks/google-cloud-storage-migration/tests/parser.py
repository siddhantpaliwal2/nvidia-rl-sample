#!/usr/bin/env python3
"""Normalize the hermetic Groovy verifier report for Harbor."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    path = Path(sys.argv[1])
    if not path.is_file():
        print(json.dumps({"tests": []}, indent=2))
        return 0
    try:
        report = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        report = {"tests": []}
    tests = [
        {"name": item.get("name", ""), "status": item.get("status", "failed")}
        for item in report.get("tests", [])
        if item.get("name")
    ]
    print(json.dumps({"tests": tests}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
