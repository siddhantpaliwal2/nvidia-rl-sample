#!/bin/sh
set -u

REPO_DIR=""
for d in /app /testbed; do
    if [ -f "$d/package.json" ] && [ -f "$d/tsconfig.json" ]; then
        REPO_DIR="$d"
        break
    fi
done
[ -n "$REPO_DIR" ] || { echo "run_script.sh: repository not found" >&2; exit 2; }
cd "$REPO_DIR"

rm -f /tmp/jest-unit.json
npx jest --runInBand --silent --json --outputFile=/tmp/jest-unit.json \
    src/emailinfra/emailinfra.gold.spec.ts \
    src/email-reply-agent/entities/entity.spec.ts 2>&1 || true
