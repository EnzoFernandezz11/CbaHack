"""Train and evaluate an Ultralytics YOLO26 detector on the peanut dataset."""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from check_training_environment import collect_environment
from prepare_yolo_dataset import prepare_yolo_dataset


# ---------------------------------------------------------------------------
# CONFIGURACIÓN EDITABLE DEL ENTRENAMIENTO
# ---------------------------------------------------------------------------
DATASET_PERCENT = 100.0
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15

MODEL = "yolo26n.pt"
EPOCHS = 100
IMAGE_SIZE = 640
GPU_BATCH_SIZE = -1
CPU_BATCH_SIZE = 4
PATIENCE = 20
GPU_WORKERS = 4
CPU_WORKERS = 0
SEED = 42
DEVICE = "auto"
RUN_NAME = "yolo26n-peanut"
RUN_TEST_EVALUATION = True

OPTIMIZER = "auto"
LEARNING_RATE = None
CACHE_IMAGES = False
AMP = True
PLOTS = True
MOSAIC = 0.5
MIXUP = 0.0
COPY_PASTE = 0.0
DETERMINISTIC = True
# ---------------------------------------------------------------------------


SCRIPT_DIR = Path(__file__).resolve().parent
CV_ROOT = SCRIPT_DIR.parent
SOURCE_DATASET = CV_ROOT / "Datasets" / "peanut_tifton_patch_v4_grouped"
WORKING_DATASETS = CV_ROOT / "Datasets" / "yolo26_working"
MODELS_ROOT = CV_ROOT / "Models-Roboflow"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Prepara un subset configurable, entrena YOLO26 y guarda métricas "
            "bajo cv/Models-Roboflow."
        )
    )
    parser.add_argument("--dataset-percent", type=float, default=DATASET_PERCENT)
    parser.add_argument("--train-ratio", type=float, default=TRAIN_RATIO)
    parser.add_argument("--val-ratio", type=float, default=VAL_RATIO)
    parser.add_argument("--test-ratio", type=float, default=TEST_RATIO)
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--imgsz", type=int, default=IMAGE_SIZE)
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--patience", type=int, default=PATIENCE)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--device", default=DEVICE)
    parser.add_argument("--run-name", default=RUN_NAME)
    parser.add_argument(
        "--test-evaluation",
        action=argparse.BooleanOptionalAction,
        default=RUN_TEST_EVALUATION,
    )
    parser.add_argument(
        "--plots",
        action=argparse.BooleanOptionalAction,
        default=PLOTS,
    )
    parser.add_argument(
        "--amp",
        action=argparse.BooleanOptionalAction,
        default=AMP,
    )
    parser.add_argument("--rebuild-dataset", action="store_true")
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if not math.isfinite(args.dataset_percent) or not 0 < args.dataset_percent <= 100:
        raise ValueError("--dataset-percent debe estar entre 0 (exclusivo) y 100.")
    ratios = (args.train_ratio, args.val_ratio, args.test_ratio)
    if any(not math.isfinite(value) or value <= 0 for value in ratios):
        raise ValueError("Todos los ratios deben ser positivos y finitos.")
    if not math.isclose(sum(ratios), 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("Los ratios train/val/test deben sumar exactamente 1.0.")
    if args.epochs < 1:
        raise ValueError("--epochs debe ser al menos 1.")
    if args.imgsz < 32:
        raise ValueError("--imgsz debe ser al menos 32.")
    if args.batch is not None and args.batch != -1 and args.batch < 1:
        raise ValueError("--batch debe ser -1 o un entero positivo.")
    if args.workers is not None and args.workers < 0:
        raise ValueError("--workers no puede ser negativo.")
    if args.patience < 0:
        raise ValueError("--patience no puede ser negativo.")


def reserve_run_directory(base: Path, requested_name: str) -> Path:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", requested_name).strip(".-")
    if not safe_name:
        raise ValueError("RUN_NAME no contiene caracteres utilizables.")
    base.mkdir(parents=True, exist_ok=True)
    candidate = base / safe_name
    suffix = 2
    while candidate.exists():
        candidate = base / f"{safe_name}_{suffix:02d}"
        suffix += 1
    candidate.mkdir()
    return candidate


def configure_logger(run_directory: Path) -> logging.Logger:
    logger = logging.getLogger("yolo26_training")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    file_handler = logging.FileHandler(run_directory / "training.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(console)
    logger.addHandler(file_handler)
    return logger


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if hasattr(value, "item"):
        try:
            return json_safe(value.item())
        except (ValueError, TypeError):
            pass
    if hasattr(value, "tolist"):
        try:
            return json_safe(value.tolist())
        except (ValueError, TypeError):
            pass
    return str(value)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(json_safe(payload), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def choose_device(torch: Any, requested: str) -> tuple[str, str]:
    normalized = str(requested).strip().lower()
    mps_backend = getattr(torch.backends, "mps", None)
    mps_available = bool(mps_backend and mps_backend.is_available())
    if normalized == "auto":
        if torch.cuda.is_available():
            return "0", f"cuda:0 ({torch.cuda.get_device_name(0)})"
        if mps_available:
            return "mps", "Apple MPS"
        return "cpu", "CPU"
    if normalized == "cpu":
        return "cpu", "CPU forzada"
    if normalized == "mps":
        if not mps_available:
            raise RuntimeError("Se solicitó MPS, pero PyTorch no lo tiene disponible.")
        return "mps", "Apple MPS"
    if normalized in {"cuda", "cuda:0"}:
        normalized = "0"
    if normalized.replace(",", "").isdigit():
        if not torch.cuda.is_available():
            raise RuntimeError(
                f"Se solicitó CUDA ({requested}), pero torch.cuda.is_available() es False."
            )
        return normalized, f"CUDA {normalized}"
    raise ValueError(f"DEVICE no reconocido: {requested!r}")


@contextmanager
def working_directory(path: Path) -> Iterator[None]:
    previous = Path.cwd()
    path.mkdir(parents=True, exist_ok=True)
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def load_model(YOLO: Any, model_spec: str, logger: logging.Logger) -> Any:
    candidate = Path(model_spec).expanduser()
    if candidate.is_file():
        logger.info("Cargando pesos locales: %s", candidate.resolve())
        return YOLO(str(candidate.resolve()))
    if candidate.is_absolute() or candidate.parent != Path("."):
        raise FileNotFoundError(f"No existen los pesos configurados: {candidate}")

    weights_directory = MODELS_ROOT / "pretrained"
    local_weight = weights_directory / candidate.name
    if local_weight.is_file():
        logger.info("Cargando pesos preentrenados cacheados: %s", local_weight)
        return YOLO(str(local_weight))

    logger.info("Los pesos %s no están cacheados; Ultralytics los descargará.", model_spec)
    with working_directory(weights_directory):
        return YOLO(model_spec)


def extract_metrics(metrics: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "results_dict": json_safe(getattr(metrics, "results_dict", {})),
        "speed_ms_per_image": json_safe(getattr(metrics, "speed", {})),
        "save_dir": json_safe(getattr(metrics, "save_dir", None)),
    }
    box = getattr(metrics, "box", None)
    if box is not None:
        for output_name, attribute in (
            ("precision", "mp"),
            ("recall", "mr"),
            ("map50", "map50"),
            ("map75", "map75"),
            ("map50_95", "map"),
            ("map50_95_per_class", "maps"),
        ):
            if hasattr(box, attribute):
                payload[output_name] = json_safe(getattr(box, attribute))
    return payload


def save_dependency_freeze(destination: Path, logger: logging.Logger) -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode == 0:
        destination.write_text(completed.stdout, encoding="utf-8")
    else:
        logger.warning("No se pudo guardar pip freeze: %s", completed.stderr.strip())


def main() -> int:
    args = parse_args()
    validate_args(args)
    run_directory = reserve_run_directory(MODELS_ROOT, args.run_name)
    logger = configure_logger(run_directory)
    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    summary: dict[str, Any] = {
        "status": "running",
        "started_at": started_at.isoformat(),
        "run_directory": run_directory,
        "requested_arguments": vars(args),
    }

    logger.info("=" * 72)
    logger.info("PIPELINE DE ENTRENAMIENTO YOLO26")
    logger.info("Directorio de corrida: %s", run_directory)
    logger.info("Python: %s", platform.python_version())
    logger.info("Ejecutable: %s", sys.executable)
    logger.info("Sistema: %s", platform.platform())

    try:
        environment, problems, warnings = collect_environment()
        write_json(
            run_directory / "environment.json",
            {"environment": environment, "warnings": warnings, "problems": problems},
        )
        save_dependency_freeze(run_directory / "dependencies-freeze.txt", logger)
        for warning in warnings:
            logger.warning(warning)
        if problems:
            raise RuntimeError("Entorno no apto: " + " | ".join(problems))

        import torch
        import ultralytics
        from ultralytics import YOLO

        device, device_description = choose_device(torch, args.device)
        uses_accelerator = device != "cpu"
        effective_batch = (
            args.batch
            if args.batch is not None
            else GPU_BATCH_SIZE
            if uses_accelerator
            else CPU_BATCH_SIZE
        )
        effective_workers = (
            args.workers
            if args.workers is not None
            else GPU_WORKERS
            if uses_accelerator
            else CPU_WORKERS
        )
        effective_amp = bool(args.amp and device not in {"cpu", "mps"})
        if device == "cpu":
            logger.warning(
                "No se detectó CUDA. El entrenamiento funcionará en CPU, pero puede ser lento."
            )

        effective_config = {
            "dataset_percent": args.dataset_percent,
            "ratios": {
                "train": args.train_ratio,
                "val": args.val_ratio,
                "test": args.test_ratio,
            },
            "model": args.model,
            "epochs": args.epochs,
            "image_size": args.imgsz,
            "batch": effective_batch,
            "patience": args.patience,
            "workers": effective_workers,
            "seed": args.seed,
            "device": device,
            "device_description": device_description,
            "optimizer": OPTIMIZER,
            "learning_rate": LEARNING_RATE,
            "cache_images": CACHE_IMAGES,
            "amp": effective_amp,
            "plots": args.plots,
            "mosaic": MOSAIC,
            "mixup": MIXUP,
            "copy_paste": COPY_PASTE,
            "deterministic": DETERMINISTIC,
            "ultralytics_version": ultralytics.__version__,
            "torch_version": torch.__version__,
        }
        write_json(run_directory / "requested_config.json", effective_config)
        logger.info("Ultralytics: %s", ultralytics.__version__)
        logger.info("PyTorch: %s", torch.__version__)
        logger.info("Dispositivo efectivo: %s", device_description)
        logger.info("Batch efectivo: %s", effective_batch)
        logger.info("Workers efectivos: %s", effective_workers)
        logger.info("AMP efectivo: %s", effective_amp)

        prepared = prepare_yolo_dataset(
            source=SOURCE_DATASET,
            output_root=WORKING_DATASETS,
            dataset_percent=args.dataset_percent,
            ratios={
                "train": args.train_ratio,
                "val": args.val_ratio,
                "test": args.test_ratio,
            },
            seed=args.seed,
            logger=logger,
            rebuild=args.rebuild_dataset,
        )
        shutil.copy2(prepared.manifest, run_directory / "subset_manifest.json")
        logger.info("Subset total: %d imágenes", prepared.total_images)
        logger.info("Distribución efectiva: %s", prepared.split_counts)

        logger.info("=" * 72)
        logger.info("CARGA DEL MODELO")
        model = load_model(YOLO, args.model, logger)
        logger.info("Modelo cargado correctamente: %s", args.model)

        train_arguments: dict[str, Any] = {
            "data": str(prepared.data_yaml),
            "epochs": args.epochs,
            "imgsz": args.imgsz,
            "batch": effective_batch,
            "patience": args.patience,
            "workers": effective_workers,
            "seed": args.seed,
            "deterministic": DETERMINISTIC,
            "device": device,
            "project": str(MODELS_ROOT),
            "name": run_directory.name,
            "exist_ok": True,
            "optimizer": OPTIMIZER,
            "cache": CACHE_IMAGES,
            "amp": effective_amp,
            "plots": args.plots,
            "mosaic": MOSAIC,
            "mixup": MIXUP,
            "copy_paste": COPY_PASTE,
            "save": True,
            "val": True,
            "verbose": True,
        }
        if LEARNING_RATE is not None:
            train_arguments["lr0"] = LEARNING_RATE
        write_json(run_directory / "train_arguments.json", train_arguments)

        logger.info("=" * 72)
        logger.info("INICIO DEL ENTRENAMIENTO")
        logger.info("Epochs=%d, imgsz=%d, dataset=%s", args.epochs, args.imgsz, prepared.data_yaml)
        model.train(**train_arguments)
        logger.info("ENTRENAMIENTO FINALIZADO")

        trainer = getattr(model, "trainer", None)
        best_checkpoint = Path(str(getattr(trainer, "best", ""))).resolve()
        last_checkpoint = Path(str(getattr(trainer, "last", ""))).resolve()
        if not best_checkpoint.is_file():
            if last_checkpoint.is_file():
                logger.warning("No se encontró best.pt; se evaluará last.pt.")
                best_checkpoint = last_checkpoint
            else:
                raise FileNotFoundError("El entrenamiento no produjo best.pt ni last.pt.")
        logger.info("Mejor checkpoint: %s", best_checkpoint)
        logger.info("Último checkpoint: %s", last_checkpoint)

        evaluation_batch = 1 if effective_batch == -1 else max(1, int(effective_batch))
        evaluation_model = YOLO(str(best_checkpoint))
        metrics_payload: dict[str, Any] = {}
        splits_to_evaluate = ["val"]
        if args.test_evaluation:
            splits_to_evaluate.append("test")

        for split in splits_to_evaluate:
            logger.info("=" * 72)
            logger.info("EVALUACIÓN EXPLÍCITA SOBRE %s", split.upper())
            metrics = evaluation_model.val(
                data=str(prepared.data_yaml),
                split=split,
                imgsz=args.imgsz,
                batch=evaluation_batch,
                workers=effective_workers,
                device=device,
                project=str(run_directory / "evaluation"),
                name=split,
                exist_ok=True,
                plots=args.plots,
                verbose=True,
            )
            extracted = extract_metrics(metrics)
            metrics_payload[split] = extracted
            write_json(run_directory / f"{split}_metrics.json", extracted)
            logger.info(
                "%s -> precision=%s, recall=%s, mAP50=%s, mAP50-95=%s",
                split,
                extracted.get("precision"),
                extracted.get("recall"),
                extracted.get("map50"),
                extracted.get("map50_95"),
            )

        summary.update(
            {
                "status": "completed",
                "effective_config": effective_config,
                "dataset": {
                    "directory": prepared.directory,
                    "data_yaml": prepared.data_yaml,
                    "total_images": prepared.total_images,
                    "split_counts": prepared.split_counts,
                },
                "checkpoints": {
                    "best": best_checkpoint,
                    "last": last_checkpoint,
                },
                "metrics": metrics_payload,
            }
        )
        logger.info("Pipeline completado correctamente.")
        return 0
    except Exception as error:
        summary.update(
            {
                "status": "failed",
                "error_type": type(error).__name__,
                "error": str(error),
            }
        )
        logger.exception("El pipeline falló: %s", error)
        raise
    finally:
        finished_at = datetime.now(timezone.utc)
        summary["finished_at"] = finished_at.isoformat()
        summary["duration_seconds"] = round(time.perf_counter() - started_clock, 3)
        write_json(run_directory / "run_summary.json", summary)
        logger.info("Duración total: %.2f segundos", summary["duration_seconds"])
        logger.info("Resumen: %s", run_directory / "run_summary.json")
        logger.info("=" * 72)


if __name__ == "__main__":
    raise SystemExit(main())
