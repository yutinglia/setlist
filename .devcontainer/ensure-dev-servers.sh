#!/usr/bin/env bash
# Ensure API + Vite are listening inside the Dev Container app service.
#
# Must survive both:
# - container entrypoint (preferred)
# - postStartCommand via `docker exec -t` (SIGHUP on shell exit)
# Pattern: trap '' HUP; setsid nohup ... & sleep 1
# https://code.visualstudio.com/remote/advancedcontainers/start-processes
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${TMPDIR:-/tmp}/vks-dev"
mkdir -p "$LOG_DIR"

# Node feature installs under nvm; keep PATH usable for non-login shells.
export PATH="/usr/local/share/nvm/current/bin:/usr/local/bin:${PATH}"
export APP_ENV="${APP_ENV:-dev}"
export WATCHFILES_FORCE_POLLING="${WATCHFILES_FORCE_POLLING:-true}"
export CHOKIDAR_USEPOLLING="${CHOKIDAR_USEPOLLING:-true}"

# Ignore HUP in this shell so background children inherit SIG_IGN before fork.
trap '' HUP

ensure_python_deps() {
  if ! python -c "import fastapi, uvicorn" >/dev/null 2>&1; then
    echo "[vks] installing Python deps..."
    pip install -r "$ROOT/data_updater/requirements.txt"
  fi
}

ensure_frontend_deps() {
  if [[ ! -x "$ROOT/frontend/node_modules/.bin/vite" ]]; then
    echo "[vks] installing frontend deps..."
    npm --prefix "$ROOT/frontend" install
  fi
}

port_open() {
  local port="$1"
  python - "$port" <<'PY'
import socket, sys
port = int(sys.argv[1])
s = socket.socket()
s.settimeout(0.3)
try:
    s.connect(("127.0.0.1", port))
except OSError:
    sys.exit(1)
finally:
    s.close()
PY
}

daemonize() {
  # New session + nohup so the process outlives TTY exec teardown.
  setsid nohup bash -c "$1" >>"$2" 2>&1 </dev/null &
  sleep 1
}

start_api() {
  if port_open 8000; then
    echo "[vks] API already on :8000"
    return
  fi
  echo "[vks] starting uvicorn on :8000"
  : >"$LOG_DIR/uvicorn.log"
  daemonize \
    "cd '$ROOT/data_updater' && exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-dir ." \
    "$LOG_DIR/uvicorn.log"
}

start_vite() {
  if port_open 5173; then
    echo "[vks] Vite already on :5173"
    return
  fi
  echo "[vks] starting Vite on :5173"
  : >"$LOG_DIR/vite.log"
  daemonize \
    "cd '$ROOT/frontend' && exec npm run dev -- --host 0.0.0.0 --port 5173" \
    "$LOG_DIR/vite.log"
}

wait_for_port() {
  local port="$1"
  local name="$2"
  local i
  for i in $(seq 1 60); do
    if port_open "$port"; then
      echo "[vks] $name ready on :$port"
      return 0
    fi
    sleep 0.5
  done
  echo "[vks] warning: $name not listening on :$port (see $LOG_DIR/)" >&2
  tail -n 40 "$LOG_DIR"/*.log 2>/dev/null || true
  return 0
}

ensure_python_deps
ensure_frontend_deps
start_api
start_vite
wait_for_port 8000 API
wait_for_port 5173 Vite
