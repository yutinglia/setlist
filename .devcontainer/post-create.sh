#!/usr/bin/env bash
set -euo pipefail

readonly WORKSPACE="/workspace"
readonly FRONTEND_NODE_MODULES="${WORKSPACE}/frontend/node_modules"

# The named volume is initially owned by root. The Dev Container terminal and
# lifecycle commands run as `vscode`, so make the dependency directory writable.
sudo install -d \
  -o "$(id -u)" \
  -g "$(id -g)" \
  "${FRONTEND_NODE_MODULES}"

npm --prefix "${WORKSPACE}/frontend" ci

python -c "import fastapi, sqlalchemy, uvicorn"
node --version
npm --version
