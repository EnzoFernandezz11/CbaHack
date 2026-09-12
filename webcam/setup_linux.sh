#!/usr/bin/env bash
set -euo pipefail

web_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "$web_root/.." && pwd)"
python_bin="${CV_PYTHON:-/opt/cv-yolo/venv/bin/python}"
runtime_deps="$web_root/.runtime-deps"

if [[ ! -x "$python_bin" ]]; then
  echo "No existe el Python de YOLO: $python_bin" >&2
  echo "Defina CV_PYTHON con la ruta correcta." >&2
  exit 1
fi

"$python_bin" -c 'import cv2, torch, ultralytics; print("Entorno YOLO disponible")'
"$python_bin" -m pip install --upgrade --target "$runtime_deps" -r "$web_root/requirements.txt"

env PYTHONPATH="$runtime_deps" \
  "$python_bin" -m pytest -c "$web_root/pytest.ini" "$web_root/tests" -q

echo "Entorno web listo. Ejecute: $repository_root/webcam/run_linux.sh"
