#!/usr/bin/env bash
set -euo pipefail

readonly WORKSPACE="/workspace"
readonly RUNTIME_DIR="/tmp/vtuber-karaoke-search-dev"

mkdir -p "${RUNTIME_DIR}"

start_service() {
  local name="$1"
  local working_directory="$2"
  shift 2

  local pid_file="${RUNTIME_DIR}/${name}.pid"
  local log_file="${RUNTIME_DIR}/${name}.log"

  if [[ -f "${pid_file}" ]]; then
    local existing_pid
    existing_pid="$(<"${pid_file}")"
    if kill -0 "${existing_pid}" 2>/dev/null; then
      echo "${name} is already running (PID ${existing_pid})."
      return
    fi
  fi

  (
    cd "${working_directory}"
    # Lifecycle commands run in a short-lived editor shell. Give each server
    # its own session so descendants (notably Vite/Node) are not terminated
    # when that shell closes. --wait keeps the tracked PID alive for as long
    # as the server process.
    nohup setsid --fork --wait "$@" >>"${log_file}" 2>&1 </dev/null &
    echo "$!" >"${pid_file}"
  )

  local started_pid
  started_pid="$(<"${pid_file}")"
  sleep 1
  if ! kill -0 "${started_pid}" 2>/dev/null; then
    echo "Failed to start ${name}. Recent log output:" >&2
    tail -n 20 "${log_file}" >&2 || true
    return 1
  fi

  echo "Started ${name} (PID ${started_pid}); log: ${log_file}"
}

start_service \
  "backend" \
  "${WORKSPACE}/data_updater" \
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload

start_service \
  "frontend" \
  "${WORKSPACE}/frontend" \
  ./node_modules/.bin/vite --host 0.0.0.0 --port 5173
