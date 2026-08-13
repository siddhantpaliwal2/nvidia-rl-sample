#!/bin/sh
set -u

REPO_DIR=""
for d in /app /testbed; do
    if [ -f "$d/package.json" ] && [ -f "$d/jest.unit.config.json" ]; then
        REPO_DIR="$d"
        break
    fi
done
[ -n "$REPO_DIR" ] || { echo "run_script.sh: repository not found" >&2; exit 2; }
cd "$REPO_DIR"

rm -f /tmp/jest-unit.json
npx jest --config ./jest.unit.config.json --runInBand --forceExit --silent --json \
    --outputFile=/tmp/jest-unit.json \
    src/appControllerHistorical.gold.spec.ts \
    src/measurement-config/datastoreMeasurement.gold.spec.ts 2>&1 || true
