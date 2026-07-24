#!/usr/bin/env bash
# Container entrypoint: start API + Vite as daemons, then run the compose command
# (usually `sleep infinity` for the Dev Container).
#
# Starting from the container entrypoint avoids the postStartCommand pitfall where
# `docker exec -t` tears down background jobs with SIGHUP when the shell exits.
# https://code.visualstudio.com/remote/advancedcontainers/start-processes
set -euo pipefail

if [[ -x /workspace/.devcontainer/ensure-dev-servers.sh ]]; then
  # Do not fail container start if deps/servers hiccup; IDE still needs sleep infinity.
  /workspace/.devcontainer/ensure-dev-servers.sh || \
    echo "[vks] ensure-dev-servers failed (container will still start)" >&2
else
  echo "[vks] ensure-dev-servers.sh missing; skipping auto-start" >&2
fi

exec "$@"
