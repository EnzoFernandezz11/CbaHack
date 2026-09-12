#!/usr/bin/env bash
set -euo pipefail

web_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cloudflared_bin="${CLOUDFLARED_BIN:-$web_root/.runtime-bin/cloudflared}"
server_port="${WEB_PORT:-8000}"

if [[ ! -x "$cloudflared_bin" ]]; then
  if command -v cloudflared >/dev/null 2>&1; then
    cloudflared_bin="$(command -v cloudflared)"
  else
    echo "No se encontró cloudflared en $cloudflared_bin ni en PATH." >&2
    exit 1
  fi
fi

exec "$cloudflared_bin" tunnel --url "http://127.0.0.1:$server_port" --no-autoupdate
