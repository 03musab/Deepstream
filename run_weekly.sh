#!/bin/bash
# Deepstream weekly signal runner.
#
# Generates the latest signals, rebuilds the walk-forward track record, and
# refreshes the site assets. If Telegram credentials are configured, also
# delivers the weekly report to subscribers.
#
# Usage:
#   ./run_weekly.sh                 full run (fetch + optimize + backtest)
#   ./run_weekly.sh --skip-pipeline use existing data (faster, offline-safe)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Load environment (Telegram credentials, etc.) from .env if present.
if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

EXTRA_ARGS="${1:-}"
if [ "$EXTRA_ARGS" = "--skip-pipeline" ]; then
    EXTRA_ARGS="--skip-pipeline"
fi

echo "=== Deepstream weekly run: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

python3 -m deepstream run $EXTRA_ARGS

# Deliver to Telegram (no-op if credentials are unset).
python3 -m deepstream.telegram

echo "=== Deepstream weekly run complete ==="
