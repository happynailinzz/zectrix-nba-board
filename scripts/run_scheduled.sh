#!/bin/sh
# zectrix-nba-board scheduled runner (cron wrapper, dynamic polling)
#
# The script itself emits POLL_MINUTES (LIVE=10 / NEXT=10|60 / FINAL=120 /
# REST=720). This wrapper remembers "<last_epoch> <poll_minutes>" in a state
# file and skips any tick that falls before the deadline, so a plain
# `*/10 * * * *` cron self-throttles to the game's natural cadence:
# game day -> frequent, off day -> ~2 refreshes per day, quiet overnight.
#
# Concurrency-protected (flock), log-capped, TZ-locked. Mirrors
# zectrix-morning-brief's wrapper conventions.
set -eu

PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PYTHON="${ZECTRIX_PYTHON:-$PROJECT_DIR/.venv/bin/python}"
SCRIPT="$PROJECT_DIR/scripts/nba_board.py"
OUTPUT="${ZECTRIX_OUTPUT:-/tmp/zectrix-nba-board.png}"
LOG="/var/log/zectrix-nba-board.log"
LOCK="/tmp/zectrix-nba-board.lock"
STATE="/var/lib/zectrix-nba-board/poll_state"   # "<epoch> <poll_minutes>"
MAX_LOG_BYTES=5242880   # 5 MB

export TZ="${ZECTRIX_TIMEZONE:-Asia/Shanghai}"

if [ ! -x "$PYTHON" ]; then
    echo "$(date '+%F %T') ERROR: Python not found at $PYTHON" >&2
    echo "Create the venv first: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
    exit 1
fi
mkdir -p "$(dirname "$STATE")"

# --- log size cap -----------------------------------------------------------
if [ -f "$LOG" ]; then
    size=$(wc -c < "$LOG" 2>/dev/null || echo 0)
    if [ "$size" -gt "$MAX_LOG_BYTES" ]; then
        tail -c 1048576 "$LOG" > "$LOG.tmp" && cat "$LOG.tmp" > "$LOG" && rm -f "$LOG.tmp"
    fi
fi

# --- concurrency guard (two ticks must never overlap) ----------------------
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "$(date '+%F %T') SKIP: another nba-board run is in progress" >> "$LOG"
    exit 0
fi

# --- dynamic-poll gate: skip if the previous interval has not elapsed ------
last_epoch=0
last_poll=60
if [ -f "$STATE" ]; then
    read -r last_epoch last_poll < "$STATE" 2>/dev/null || { last_epoch=0; last_poll=60; }
    case "$last_epoch" in
        ''|*[!0-9]*) last_epoch=0 ;;
    esac
    case "$last_poll" in
        ''|*[!0-9]*) last_poll=60 ;;
    esac
fi
now_epoch=$(date +%s)
deadline=$(( last_epoch + last_poll * 60 ))
if [ "$now_epoch" -lt "$deadline" ]; then
    due_at=$(date -d "@$deadline" '+%F %T' 2>/dev/null || echo '?')
    echo "$(date '+%F %T') SKIP: poll not due until $due_at (last interval $last_poll min)" >> "$LOG"
    exit 0
fi

# --- run ---------------------------------------------------------------------
cd "$PROJECT_DIR"
run_out="$( "$PYTHON" "$SCRIPT" --output "$OUTPUT" 2>>"$LOG" )" || {
    printf '%s\n' "$run_out" >> "$LOG"
    echo "$(date '+%F %T') run failed; state unchanged, will retry on the next tick" >> "$LOG"
    exit 1
}
poll=$(printf '%s\n' "$run_out" | grep -oE 'POLL_MINUTES=[0-9]+' | tail -1 | cut -d= -f2 || true)
case "$poll" in
    ''|*[!0-9]*) poll=60 ;;
esac
printf '%s\n' "$run_out" >> "$LOG"
echo "$(date '+%F %T') ok POLL_MINUTES=$poll" >> "$LOG"
echo "$(date +%s) $poll" > "$STATE"
exit 0
