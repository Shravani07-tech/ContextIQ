#!/usr/bin/env bash
# run-dev.sh — one-command ContextIQ dev environment (Linux/macOS).
#
#   ./run-dev.sh          start backend (:8000) + frontend (:3000)
#   ./run-dev.sh stop     stop both dev servers
#
# Mirrors run-dev.ps1: anchored to the project root, deterministic
# ports (stale dev processes are cleaned first, so Next never drifts
# to :3001 and breaks CORS), detached servers with logs in .dev/,
# and real health checks before declaring success.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

BACKEND_PORT=8000
FRONTEND_PORT=3000

free_port() {
  local pids
  pids=$(lsof -ti "tcp:$1" 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "  freeing port $1 (PID(s): $pids)"
    kill $pids 2>/dev/null || true
    sleep 1
    kill -9 $pids 2>/dev/null || true
  fi
}

wait_for_http() { # url timeout_sec label
  local deadline=$(( $(date +%s) + $2 ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    if curl -sf -o /dev/null --max-time 3 "$1"; then
      echo "  $3 is up: $1"
      return 0
    fi
    sleep 2
  done
  echo "WARNING: $3 did not respond within $2s — check .dev/ logs" >&2
  return 1
}

if [ "${1:-}" = "stop" ]; then
  echo "Stopping ContextIQ dev servers..."
  free_port "$BACKEND_PORT"
  free_port "$FRONTEND_PORT"
  echo "Done."
  exit 0
fi

echo "ContextIQ dev environment"
echo "=========================="

# --- Preflight checks -------------------------------------------------------
for tool in python node npm curl; do
  command -v "$tool" >/dev/null || { echo "ERROR: '$tool' is not on PATH." >&2; exit 1; }
done

if curl -sf -o /dev/null --max-time 3 "http://localhost:11434/api/tags"; then
  echo "  Ollama: running"
else
  echo "WARNING: Ollama is not reachable on :11434 — chat answers will fail until it is started." >&2
fi

if [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "  frontend/node_modules missing — running npm install..."
  (cd "$ROOT/frontend" && npm install)
fi

# --- Clean ports, then launch ------------------------------------------------
echo "Cleaning ports..."
free_port "$BACKEND_PORT"
free_port "$FRONTEND_PORT"

mkdir -p "$ROOT/.dev"

echo "Starting backend on :$BACKEND_PORT ..."
nohup python -m uvicorn api.main:app --port "$BACKEND_PORT" \
  > "$ROOT/.dev/backend.out.log" 2> "$ROOT/.dev/backend.err.log" &
echo $! > "$ROOT/.dev/backend.pid"

# Backend warm-up loads the embedding model and may revalidate its
# HuggingFace cache over the network — allow 240s before giving up.
backend_ok=0
wait_for_http "http://localhost:$BACKEND_PORT/health" 240 "Backend" && backend_ok=1

echo "Starting frontend on :$FRONTEND_PORT ..."
(cd "$ROOT/frontend" && nohup npm run dev -- -p "$FRONTEND_PORT" \
  > "$ROOT/.dev/frontend.out.log" 2> "$ROOT/.dev/frontend.err.log" &
  echo $! > "$ROOT/.dev/frontend.pid")

frontend_ok=0
wait_for_http "http://localhost:$FRONTEND_PORT" 90 "Frontend" && frontend_ok=1

echo ""
if [ "$backend_ok" = 1 ] && [ "$frontend_ok" = 1 ]; then
  echo "ContextIQ is running"
  echo "  App:      http://localhost:$FRONTEND_PORT"
  echo "  API:      http://localhost:$BACKEND_PORT"
  echo "  API docs: http://localhost:$BACKEND_PORT/docs"
  echo "  Logs:     $ROOT/.dev/"
  echo "  Stop:     ./run-dev.sh stop"
else
  echo "ERROR: startup incomplete — see logs in $ROOT/.dev/" >&2
  exit 1
fi
