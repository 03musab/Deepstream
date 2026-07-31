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

# Pick a working Python interpreter (Windows Git Bash: `python`; POSIX: `python3`).
if command -v python >/dev/null 2>&1; then
    PYTHON_BIN=python
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
else
    echo "No Python interpreter found (tried 'python' and 'python3')" >&2
    exit 1
fi

echo "=== Deepstream weekly run: $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

"$PYTHON_BIN" -m deepstream run $EXTRA_ARGS

# Deliver to Telegram (no-op if credentials are unset).
"$PYTHON_BIN" -m deepstream.telegram

echo "=== Deepstream weekly run complete ==="
