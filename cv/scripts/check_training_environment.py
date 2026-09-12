"""Report whether the current Python environment can train Ultralytics YOLO26."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import re
import shutil
import sys
from pathlib import Path
from typing import Any


MINIMUM_PYTHON = (3, 10)
MINIMUM_ULTRALYTICS = (8, 4, 0)


def _version_tuple(value: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", value)
    return tuple(int(item) for item in numbers[:3])


def collect_environment() -> tuple[dict[str, Any], list[str], list[str]]:
    problems: list[str] = []
    warnings: list[str] = []
    report: dict[str, Any] = {
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
            "supported": sys.version_info[:2] >= MINIMUM_PYTHON,
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "description": platform.platform(),
        },
        "commands": {
            "nvidia_smi": shutil.which("nvidia-smi"),
        },
        "packages": {},
        "accelerators": {},
    }

    if not report["python"]["supported"]:
        problems.append(
            f"Se requiere Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]} o superior."
        )

    for package in ("torch", "torchvision", "ultralytics", "yaml", "PIL"):
        distribution = {"yaml": "PyYAML", "PIL": "Pillow"}.get(package, package)
        try:
            report["packages"][distribution] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            report["packages"][distribution] = None
            problems.append(f"Falta la dependencia Python: {distribution}")

    ultralytics_version = report["packages"].get("ultralytics")
    if ultralytics_version and _version_tuple(ultralytics_version) < MINIMUM_ULTRALYTICS:
        problems.append(
            "Ultralytics es demasiado antiguo para YOLO26: "
            f"{ultralytics_version}; mínimo esperado "
            f"{'.'.join(str(item) for item in MINIMUM_ULTRALYTICS)}."
        )

    torch_version = report["packages"].get("torch")
    if torch_version:
        try:
            import torch

            cuda_available = bool(torch.cuda.is_available())
            report["accelerators"]["cuda_available"] = cuda_available
            report["accelerators"]["torch_cuda_runtime"] = torch.version.cuda
            report["accelerators"]["cudnn_version"] = (
                torch.backends.cudnn.version() if torch.backends.cudnn.is_available() else None
            )
            report["accelerators"]["cuda_device_count"] = torch.cuda.device_count()
            report["accelerators"]["cuda_devices"] = []
            if cuda_available:
                for index in range(torch.cuda.device_count()):
                    properties = torch.cuda.get_device_properties(index)
                    report["accelerators"]["cuda_devices"].append(
                        {
                            "index": index,
                            "name": torch.cuda.get_device_name(index),
                            "total_memory_gb": round(properties.total_memory / 1024**3, 2),
                            "capability": list(torch.cuda.get_device_capability(index)),
                        }
                    )
            elif report["commands"]["nvidia_smi"]:
                warnings.append(
                    "nvidia-smi está disponible, pero esta instalación de PyTorch no "
                    "tiene CUDA activa. El entrenamiento usará CPU."
                )

            mps_backend = getattr(torch.backends, "mps", None)
            report["accelerators"]["mps_available"] = bool(
                mps_backend and mps_backend.is_available()
            )
            report["accelerators"]["selected_by_auto"] = (
                "cuda:0"
                if cuda_available
                else "mps"
                if report["accelerators"]["mps_available"]
                else "cpu"
            )
        except Exception as error:  # pragma: no cover - depends on local binary state
            problems.append(f"PyTorch está instalado, pero no pudo inicializarse: {error}")

    return report, problems, warnings


def print_human_report(
    report: dict[str, Any],
    problems: list[str],
    warnings: list[str],
) -> None:
    print("=" * 72)
    print("VERIFICACIÓN DEL ENTORNO DE ENTRENAMIENTO YOLO26")
    print("=" * 72)
    print(f"Python:       {report['python']['version']}")
    print(f"Ejecutable:   {report['python']['executable']}")
    print(f"Sistema:      {report['platform']['description']}")
    print("Dependencias:")
    for name, version in report["packages"].items():
        print(f"  - {name:<12} {version or 'NO INSTALADO'}")

    accelerators = report.get("accelerators", {})
    if accelerators:
        print(f"CUDA activa:  {accelerators.get('cuda_available')}")
        print(f"CUDA runtime: {accelerators.get('torch_cuda_runtime')}")
        for device in accelerators.get("cuda_devices", []):
            print(
                f"  - GPU {device['index']}: {device['name']} "
                f"({device['total_memory_gb']:.2f} GB)"
            )
        print(f"Dispositivo auto: {accelerators.get('selected_by_auto')}")

    for warning in warnings:
        print(f"ADVERTENCIA: {warning}")
    if problems:
        for problem in problems:
            print(f"ERROR: {problem}")
        print("\nEntorno NO apto. Ejecute cv/setup_training.ps1 o instale requirements-yolo26.txt.")
    else:
        print("\nEntorno apto para ejecutar el pipeline YOLO26.")
    print("=" * 72)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emitir solamente JSON")
    parser.add_argument("--output", type=Path, help="Guardar el reporte JSON en esta ruta")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report, problems, warnings = collect_environment()
    payload = {"environment": report, "warnings": warnings, "problems": problems}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_human_report(report, problems, warnings)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
