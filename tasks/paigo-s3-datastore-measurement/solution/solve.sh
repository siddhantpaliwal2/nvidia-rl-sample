#!/bin/sh
set -eu
cd /app
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
git apply "$SCRIPT_DIR/oracle.patch"
