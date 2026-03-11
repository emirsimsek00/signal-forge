#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

cd "$ROOT_DIR"

cleanup() {
  [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

if [[ ! -d .venv ]]; then
  "$PYTHON_BIN" -m venv .venv
fi
source .venv/bin/activate
pip install -e ".[dev]" >/dev/null

pushd frontend >/dev/null
npm ci >/dev/null
popd >/dev/null

echo "[start] backend on http://${BACKEND_HOST}:${BACKEND_PORT}"
uvicorn backend.main:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" >/tmp/signalforge-backend.log 2>&1 &
BACKEND_PID=$!

for _ in {1..30}; do
  if curl -fsS "http://${BACKEND_HOST}:${BACKEND_PORT}/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "[start] frontend on http://localhost:${FRONTEND_PORT}"
(
  cd frontend
  npm run dev -- --port "$FRONTEND_PORT"
) >/tmp/signalforge-frontend.log 2>&1 &
FRONTEND_PID=$!

sleep 2

if command -v open >/dev/null 2>&1; then
  open "http://localhost:${FRONTEND_PORT}"
fi

echo "SignalForge is running"
echo "- UI:      http://localhost:${FRONTEND_PORT}"
echo "- Backend: http://${BACKEND_HOST}:${BACKEND_PORT}"
echo "Logs: /tmp/signalforge-backend.log and /tmp/signalforge-frontend.log"
echo "Press Ctrl+C to stop both services"

wait "$FRONTEND_PID"
