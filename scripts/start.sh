#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
HOST=${TUANKB_HOST:-0.0.0.0}
PORT=${TUANKB_PORT:-18893}
LOG=${TUANKB_LOG:-/tmp/tuankb-${PORT}.log}
PIDFILE=${TUANKB_PIDFILE:-/tmp/tuankb-${PORT}.pid}

if [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "already running pid=$(cat "$PIDFILE")"
  exit 0
fi

nohup python3 server.py >"$LOG" 2>&1 &
echo $! > "$PIDFILE"
echo "started pid=$(cat "$PIDFILE") log=$LOG url=http://$HOST:$PORT"
