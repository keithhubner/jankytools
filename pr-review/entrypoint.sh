#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Run initial PR review in background (if not skipped)
if [ "${SKIP_INITIAL_RUN:-}" != "1" ]; then
    echo "Running initial PR review..."
    bash "$SCRIPT_DIR/pr-review-summary.sh" &
fi

# Start the server in foreground
exec python3 "$SCRIPT_DIR/pr-review-server.py"
