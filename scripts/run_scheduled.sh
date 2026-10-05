#!/bin/sh
# zectrix-nba-board scheduled runner (cron wrapper)
# Mirrors zectrix-morning-brief: TZ-locked, concurrency-protected, log-capped.
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON="${ZECTRIX_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
SCRIPT="$PROJECT_DIR/scripts/nba_board.py"
OUTPUT="${ZECTRIX_OUTPUT:-/tmp/zectrix-nba-board.png}"
LOG="/var/log/zectrix-nba-board.log"
LOCK="/tmp/zectrix-nba-board.lock"
MAX_LOG_BYTES=5242880   # 5 MB

export TZ="${ZECTRIX_TIMEZONE:-Asia/Shanghai}"

if [ ! -x "$PYTHON" ]; then
    echo "$(date '+%F %T') ERROR: Python not found at $PYTHON" >&2
    echo "Create the venv first: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    exit 1
fi

# --- log size cap -----------------------------------------------------------
if [ -f "$LOG" ]; then
    size=$(wc -c < "$LOG" 2>/dev/null || echo 0)
    if [ "$size" -gt "$MAX_LOG_BYTES" ]; then
        tail -c 1048576 "$LOG" > "$LOG.tmp" && cat "$LOG.tmp" > "$LOG" && rm -f "$LOG.tmp"
    fi
fi

# --- concurrency guard (one run at a time; */10 cadence can overlap) -------
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "$(date '+%F %T') SKIP: another nba-board run is in progress" >> "$LOG"
    exit 0
fi

cd "$PROJECT_DIR"
echo "----- $(date '+%F %T') run begin -----" >> "$LOG"
"$PYTHON" "$SCRIPT" --output "$OUTPUT" >> "$LOG" 2>&1
status=$?
echo "$(date '+%F %T') run end (exit $status)" >> "$LOG"
exit "$status"
