#!/bin/sh
set -u

TESTS_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REWARD_DIR="${REWARD_DIR:-/logs/verifier}"
mkdir -p "$REWARD_DIR"
REWARD=0
echo "$REWARD" > "$REWARD_DIR/reward.txt"
finish() { echo "$REWARD" > "$REWARD_DIR/reward.txt"; echo "reward: $REWARD"; }
trap finish EXIT

REPO_ROOT=""
for d in /app /testbed; do
    if [ -d "$d/.git" ] && [ -f "$d/package.json" ]; then REPO_ROOT="$d"; break; fi
done
[ -n "$REPO_ROOT" ] || { echo "test.sh: repo root not found" >&2; exit 1; }

python3 - "$TESTS_DIR/config.json" <<'PYEOF' > /tmp/gold_tests.patch
import json, sys
print(json.load(open(sys.argv[1]))["test_patch"], end="")
PYEOF

cd "$REPO_ROOT"
git apply --reverse --check /tmp/gold_tests.patch 2>/dev/null && git apply --reverse /tmp/gold_tests.patch
git apply /tmp/gold_tests.patch || { echo "test.sh: gold test patch failed" >&2; exit 1; }
sh "$TESTS_DIR/run_script.sh" > /tmp/runner_stdout.txt 2>&1
cat /tmp/runner_stdout.txt
python3 "$TESTS_DIR/parser.py" /tmp/jest-unit.json > "$REWARD_DIR/output.json"
cp /tmp/runner_stdout.txt "$REWARD_DIR/stdout.txt" 2>/dev/null || true
cat "$REWARD_DIR/output.json"
echo

if python3 - "$TESTS_DIR/config.json" "$REWARD_DIR/output.json" <<'PYEOF'
import json, sys
cfg = json.load(open(sys.argv[1])); out = json.load(open(sys.argv[2]))
verdicts = {item["name"]: item["status"] for item in out["tests"]}
required = cfg["fail_to_pass"] + cfg["pass_to_pass"]
missing = [name for name in required if verdicts.get(name) != "passed"]
print(f"required passed: {len(required) - len(missing)}/{len(required)}")
for name in missing: print(f"  NOT PASSED ({verdicts.get(name, 'not-run')}): {name}")
sys.exit(0 if not missing else 1)
PYEOF
then REWARD=1; fi
exit 0
