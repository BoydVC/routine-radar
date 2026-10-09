#!/usr/bin/env bash
# Routine Radar: ./run.sh [start|stop|status|build|test]
set -euo pipefail
cd "$(dirname "$0")"
PORT=4272; PIDF=.server.pid
status() { if [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; then echo "running: http://127.0.0.1:$PORT/ (pid $(cat "$PIDF"))"; else echo "not running"; return 1; fi; }
start() { python3 build.py; if status >/dev/null 2>&1; then status; return; fi
  setsid nohup python3 server.py > .server.log 2>&1 < /dev/null & echo $! > "$PIDF"; sleep 0.7; status
  echo "offline copy: $(pwd)/dist/routine-radar.html (open directly, no server needed)"; }
stop() { [ -f "$PIDF" ] && kill "$(cat "$PIDF")" 2>/dev/null || true; rm -f "$PIDF"; echo stopped; }
case "${1:-start}" in
  start) start;; stop) stop;; status) status;; build) python3 build.py;;
  test) python3 tests/smoke_test.py;;
  *) echo "usage: $0 start|stop|status|build|test"; exit 2;;
esac
