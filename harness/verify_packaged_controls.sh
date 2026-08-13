#!/usr/bin/env bash

set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
    echo "missing required command: docker" >&2
    exit 1
fi

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"

tasks=(
  customer-billing-schedule-migration
  customer-identity-migration
  dimension-pricing-tiers
  top-up-billing-lifecycle
  s3-datastore-measurement
  email-inbox-infrastructure
  bank-parser-consolidation
  google-cloud-storage-migration
)

control_dir=$(mktemp -d)
cleanup() {
    rm -rf "$control_dir"
}
trap cleanup EXIT

failures=0
for task_name in "${tasks[@]}"; do
    image_name="nvidia-control-$task_name"
    echo
    echo "Building $task_name"
    docker build --platform linux/amd64 -q -t "$image_name" \
        "tasks/$task_name/environment" >/dev/null

    null_log="$control_dir/$task_name-null.log"
    oracle_log="$control_dir/$task_name-oracle.log"

    docker run --rm --platform linux/amd64 \
        -v "$repo_root/tasks/$task_name/tests:/tests:ro" \
        "$image_name" sh /tests/test.sh >"$null_log" 2>&1 || true

    docker run --rm --platform linux/amd64 \
        -v "$repo_root/tasks/$task_name/tests:/tests:ro" \
        -v "$repo_root/tasks/$task_name/solution:/solution:ro" \
        "$image_name" sh -lc 'sh /solution/solve.sh && sh /tests/test.sh' \
        >"$oracle_log" 2>&1 || true

    null_reward=$(sed -n 's/^reward: //p' "$null_log" | tail -1)
    oracle_reward=$(sed -n 's/^reward: //p' "$oracle_log" | tail -1)
    printf '%-55s null=%s oracle=%s\n' \
        "$task_name" "${null_reward:-missing}" "${oracle_reward:-missing}"

    if [ "$null_reward" != "0" ] || [ "$oracle_reward" != "1" ]; then
        failures=$((failures + 1))
        echo "  control failed; null log: $null_log" >&2
        echo "  control failed; oracle log: $oracle_log" >&2
    fi
done

if [ "$failures" -ne 0 ]; then
    echo "$failures task controls failed" >&2
    exit 1
fi

echo
echo "All 8 packaged task controls passed: untouched reward 0, oracle reward 1."
