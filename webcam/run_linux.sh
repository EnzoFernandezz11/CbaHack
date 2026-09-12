#!/usr/bin/env bash
set -euo pipefail

web_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python_bin="${CV_PYTHON:-/opt/cv-yolo/venv/bin/python}"
runtime_deps="$web_root/.runtime-deps"
server_host="${WEB_HOST:-127.0.0.1}"
server_port="${WEB_PORT:-8000}"

if [[ ! -x "$python_bin" ]]; then
  echo "No existe el Python de YOLO: $python_bin" >&2
  exit 1
fi
if [[ ! -d "$runtime_deps/fastapi" ]]; then
  echo "Faltan las dependencias web. Ejecute primero: $web_root/setup_linux.sh" >&2
  exit 1
fi

exec env PYTHONPATH="$runtime_deps" "$python_bin" -m uvicorn \
  backend.main:app \
  --app-dir "$web_root" \
  --host "$server_host" \
  --port "$server_port" \
  --workers 1 \
  --ws-per-message-deflate false \
  "$@"
