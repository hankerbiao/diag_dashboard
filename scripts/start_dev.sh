#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/diag_backend"
FRONTEND_DIR="$ROOT_DIR/diag_frontend"

BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-8000}"

PIDS=()

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM

  if ((${#PIDS[@]} > 0)); then
    echo
    echo "Stopping dev servers..."
    for pid in "${PIDS[@]}"; do
      kill "$pid" 2>/dev/null || true
    done
    wait "${PIDS[@]}" 2>/dev/null || true
  fi

  exit "$exit_code"
}

require_command() {
  local command_name="$1"
  local install_hint="$2"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing command: $command_name"
    echo "$install_hint"
    exit 1
  fi
}

backend_command() {
  if [[ -x "$BACKEND_DIR/.venv/bin/uvicorn" ]]; then
    printf '%s\n' "$BACKEND_DIR/.venv/bin/uvicorn"
    return
  fi

  if command -v uvicorn >/dev/null 2>&1; then
    printf '%s\n' "uvicorn"
    return
  fi

  if command -v uv >/dev/null 2>&1; then
    printf '%s\n' "uv run uvicorn"
    return
  fi

  echo "Missing backend runner: uvicorn"
  echo "Install backend dependencies first: cd diag_backend && uv pip install -r requirements.txt"
  exit 1
}

wait_for_first_exit() {
  local pid status

  while true; do
    for pid in "${PIDS[@]}"; do
      if ! jobs -r -p | grep -q "^${pid}$"; then
        set +e
        wait "$pid"
        status=$?
        set -e
        return "$status"
      fi
    done

    sleep 1
  done
}

trap cleanup EXIT INT TERM

require_command npm "Install Node.js/npm, then run: cd diag_frontend && npm install"

port_is_listening() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN -t >/dev/null 2>&1
}

if port_is_listening "$BACKEND_PORT"; then
  requested_port="$BACKEND_PORT"
  for candidate_port in $(seq $((BACKEND_PORT + 1)) $((BACKEND_PORT + 20))); do
    if ! port_is_listening "$candidate_port"; then
      BACKEND_PORT="$candidate_port"
      break
    fi
  done

  if [[ "$BACKEND_PORT" == "$requested_port" ]]; then
    echo "No free backend port found in ${requested_port}-$((requested_port + 20))."
    exit 1
  fi
  echo "Backend port ${requested_port} is occupied; using ${BACKEND_PORT}."
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "Frontend dependencies are missing."
  echo "Run first: cd diag_frontend && npm install"
  exit 1
fi

BACKEND_RUNNER="$(backend_command)"

echo "Starting WeaveEye dev servers..."
echo "Backend:  http://localhost:${BACKEND_PORT}/docs"
echo "Frontend: http://localhost:3000"
echo

(
  cd "$BACKEND_DIR"
  if [[ "$BACKEND_RUNNER" == "uv run uvicorn" ]]; then
    uv run uvicorn app.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT"
  else
    "$BACKEND_RUNNER" app.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT"
  fi
) &
PIDS+=("$!")

(
  cd "$FRONTEND_DIR"
  VITE_API_BASE_URL="" \
    VITE_API_PROXY_TARGET="http://127.0.0.1:${BACKEND_PORT}" \
    npm run dev
) &
PIDS+=("$!")

wait_for_first_exit
