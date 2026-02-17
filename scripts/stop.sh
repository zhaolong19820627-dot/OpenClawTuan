#!/usr/bin/env bash
set -euo pipefail
PORT=${TUANKB_PORT:-18893}
PIDFILE=${TUANKB_PIDFILE:-/tmp/tuankb-${PORT}.pid}

if [[ ! -f "$PIDFILE" ]]; then
  echo "not running"
  exit 0
fi

PID=$(cat "$PIDFILE")
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  echo "stopped pid=$PID"
else
  echo "stale pidfile"
fi
rm -f "$PIDFILE"
