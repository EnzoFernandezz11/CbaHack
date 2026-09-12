"""Fine-tune the previous YOLO26 peanut detector with locally captured images."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import logging
import math
import os
import platform
import shutil
import sys
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from check_training_environment import collect_environment
from prepare_own_dataset import prepare as prepare_normalized_dataset
from train_yolo26 import (
    choose_device,
    configure_logger,
    extract_metrics,
    reserve_run_directory,
    save_dependency_freeze,
    write_json,
)


# ---------------------------------------------------------------------------
# CONFIGURACIÓN PREDETERMINADA DEL FINE-TUNING
# ---------------------------------------------------------------------------
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15
TEST_RATIO = 0.15
SEED = 42

EPOCHS = 40
IMAGE_SIZE = 768
GPU_BATCH_SIZE = -1
CPU_BATCH_SIZE = 2
PATIENCE = 12
GPU_WORKERS = 4
CPU_WORKERS = 0
DEVICE = "auto"
FREEZE_LAYERS = 10

OPTIMIZER = "AdamW"
LEARNING_RATE = 0.001
FINAL_LEARNING_RATE_FACTOR = 0.01
WEIGHT_DECAY = 0.0005
WARMUP_EPOCHS = 3.0
MOSAIC = 0.20
CLOSE_MOSAIC = 5
CACHE_IMAGES = False
AMP = True
PLOTS = True
DETERMINISTIC = True
MIN_IMAGES_PER_SOURCE_SPLIT = 2

RUN_NAME = "yolo26n-peanut-own-finetune-v1"
# ---------------------------------------------------------------------------


SCRIPT_DIR = Path(__file__).resolve().parent
CV_ROOT = SCRIPT_DIR.parent
OWN_DATASET_ROOT = CV_ROOT / "Datasets" / "FotosPropias"
NORMALIZED_ROOT = OWN_DATASET_ROOT / "prepared" / "all"
SPLITS_ROOT = OWN_DATASET_ROOT / "prepared" / "splits"
MODELS_ROOT = CV_ROOT / "Models-Roboflow"
DEFAULT_MODEL = (
    MODELS_ROOT
    / "yolo26n-peanut-50pct-50e-v1"
    / "weights"
    / "best.pt"
)
SPLITS = ("train", "val", "test")


@dataclass(frozen=True)
class CaptureGroup:
    name: str
    source: str
    images: tuple[dict[str, Any], ...]

    @property
    def image_count(self) -> int:
        return len(self.images)

    @property
    def annotation_count(self) -> int:
        return sum(int(image["annotations"]) for image in self.images)


@dataclass(frozen=True)
class GroupCandidate:
    image_counts: tuple[int, int, int]
    annotation_counts: tuple[int, int, int]
    assignments: tuple[int, ...]
    groups: tuple[CaptureGroup, ...]


@dataclass(frozen=True)
class PreparedSplit:
    directory: Path
    data_yaml: Path
    manifest: Path
    split_counts: dict[str, int]
    annotation_counts: dict[str, int]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Crea un split sin fuga de datos y ajusta el mejor checkpoint anterior "
            "con las imágenes propias."
        )
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--imgsz", type=int, default=IMAGE_SIZE)
    parser.add_argument("--batch", type=int, default=None)
    parser.add_argument("--patience", type=int, default=PATIENCE)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--device", default=DEVICE)
    parser.add_argument("--freeze", type=int, default=FREEZE_LAYERS)
    parser.add_argument("--learning-rate", type=float, default=LEARNING_RATE)
    parser.add_argument("--train-ratio", type=float, default=TRAIN_RATIO)
    parser.add_argument("--val-ratio", type=float, default=VAL_RATIO)
    parser.add_argument("--test-ratio", type=float, default=TEST_RATIO)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--run-name", default=RUN_NAME)
    parser.add_argument(
        "--baseline-evaluation",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Evalúa el checkpoint original antes de ajustarlo.",
    )
    parser.add_argument(
        "--test-evaluation",
        action=argparse.BooleanOptionalAction,
        default=True,
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
    parser.add_argument(
        "--rebuild-dataset",
        action="store_true",
        help="Reconstruye el split derivado si ya existe.",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="Valida y prepara el split sin iniciar el entrenamiento.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> dict[str, float]:
    ratios = {
        "train": args.train_ratio,
        "val": args.val_ratio,
        "test": args.test_ratio,
    }
    if any(not math.isfinite(value) or value <= 0 for value in ratios.values()):
        raise ValueError("Todos los ratios deben ser positivos y finitos.")
    if not math.isclose(sum(ratios.values()), 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("Los ratios train/val/test deben sumar exactamente 1.0.")
    if args.epochs < 1:
        raise ValueError("--epochs debe ser al menos 1.")
    if args.imgsz < 32:
        raise ValueError("--imgsz debe ser al menos 32.")
    if args.batch is not None and args.batch != -1 and args.batch < 1:
        raise ValueError("--batch debe ser -1 o un entero positivo.")
    if args.patience < 0:
        raise ValueError("--patience no puede ser negativo.")
    if args.workers is not None and args.workers < 0:
        raise ValueError("--workers no puede ser negativo.")
    if args.freeze < 0:
        raise ValueError("--freeze no puede ser negativo.")
    if not math.isfinite(args.learning_rate) or args.learning_rate <= 0:
        raise ValueError("--learning-rate debe ser positivo y finito.")
    return ratios


def _load_groups() -> tuple[list[CaptureGroup], str]:
    manifest_path = NORMALIZED_ROOT / "manifest.json"
    if not manifest_path.is_file():
        prepare_normalized_dataset()
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    images = manifest.get("images", [])
    if not images:
        raise ValueError(f"El manifiesto no contiene imágenes: {manifest_path}")

    grouped: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    prepared_names: set[str] = set()
    for image in images:
        name = str(image["prepared_name"])
        if name in prepared_names:
            raise ValueError(f"Nombre preparado duplicado en el manifiesto: {name}")
        prepared_names.add(name)
        image_path = NORMALIZED_ROOT / "images" / name
        label_path = NORMALIZED_ROOT / "labels" / f"{Path(name).stem}.txt"
        if not image_path.is_file() or not label_path.is_file():
            raise FileNotFoundError(f"Falta el par imagen/etiqueta para {name}")
        label_lines = [line for line in label_path.read_text().splitlines() if line.strip()]
        if len(label_lines) != int(image["annotations"]):
            raise ValueError(f"El conteo de cajas no coincide para {name}")
        for line in label_lines:
            values = line.split()
            if len(values) != 5 or values[0] != "0":
                raise ValueError(f"Etiqueta YOLO inválida en {label_path}: {line!r}")
            coordinates = [float(value) for value in values[1:]]
            if not all(0 <= value <= 1 for value in coordinates):
                raise ValueError(f"Coordenada fuera de rango en {label_path}: {line!r}")
            if coordinates[2] <= 0 or coordinates[3] <= 0:
                raise ValueError(f"Caja sin área en {label_path}: {line!r}")
        key = (str(image["source_collection"]), str(image["capture_group"]))
        grouped[key].append(image)

    groups = [
        CaptureGroup(
            name=group_name,
            source=source,
            images=tuple(sorted(group_images, key=lambda item: item["prepared_name"])),
        )
        for (source, group_name), group_images in sorted(grouped.items())
    ]
    if len(groups) < len(SPLITS):
        raise ValueError("No hay suficientes grupos de captura para crear los tres splits.")
    source_group_counts = Counter(group.source for group in groups)
    insufficient = [
        source for source, count in source_group_counts.items() if count < len(SPLITS)
    ]
    if insufficient:
        raise ValueError(
            "Cada fuente debe tener al menos tres grupos; insuficientes: "
            + ", ".join(insufficient)
        )
    digest = hashlib.sha256(manifest_bytes).hexdigest()
    return groups, digest


def _source_candidates(
    groups: list[CaptureGroup],
    seed: int,
) -> list[GroupCandidate]:
    ordered = tuple(
        sorted(
            groups,
            key=lambda group: hashlib.sha256(
                f"{seed}:{group.name}".encode("utf-8")
            ).hexdigest(),
        )
    )
    candidates: list[GroupCandidate] = []
    for assignments in itertools.product(range(len(SPLITS)), repeat=len(ordered)):
        if set(assignments) != set(range(len(SPLITS))):
            continue
        image_counts = [0, 0, 0]
        annotation_counts = [0, 0, 0]
        for group, split_index in zip(ordered, assignments):
            image_counts[split_index] += group.image_count
            annotation_counts[split_index] += group.annotation_count
        if min(image_counts) < MIN_IMAGES_PER_SOURCE_SPLIT:
            continue
        candidates.append(
            GroupCandidate(
                image_counts=tuple(image_counts),
                annotation_counts=tuple(annotation_counts),
                assignments=assignments,
                groups=ordered,
            )
        )
    return candidates


def assign_groups(
    groups: list[CaptureGroup],
    ratios: dict[str, float],
    seed: int,
) -> dict[str, list[CaptureGroup]]:
    """Find the most balanced assignment while keeping every group intact."""
    by_source: defaultdict[str, list[CaptureGroup]] = defaultdict(list)
    for group in groups:
        by_source[group.source].append(group)
    candidate_sets = [
        _source_candidates(source_groups, seed)
        for _, source_groups in sorted(by_source.items())
    ]

    total_images = sum(group.image_count for group in groups)
    total_annotations = sum(group.annotation_count for group in groups)
    target_images = tuple(total_images * ratios[split] for split in SPLITS)
    target_annotations = tuple(total_annotations * ratios[split] for split in SPLITS)
    best_key: tuple[Any, ...] | None = None
    best_candidates: tuple[GroupCandidate, ...] | None = None

    for combination in itertools.product(*candidate_sets):
        image_counts = tuple(
            sum(candidate.image_counts[index] for candidate in combination)
            for index in range(len(SPLITS))
        )
        annotation_counts = tuple(
            sum(candidate.annotation_counts[index] for candidate in combination)
            for index in range(len(SPLITS))
        )
        score = sum(
            ((image_counts[index] - target_images[index]) / total_images) ** 2
            + 0.25
            * (
                (annotation_counts[index] - target_annotations[index])
                / total_annotations
            )
            ** 2
            for index in range(len(SPLITS))
        )
        assignment_tie_breaker = tuple(
            candidate.assignments for candidate in combination
        )
        key = (
            score,
            tuple(
                abs(image_counts[index] - target_images[index])
                for index in range(len(SPLITS))
            ),
            assignment_tie_breaker,
        )
        if best_key is None or key < best_key:
            best_key = key
            best_candidates = combination

    if best_candidates is None:
        raise RuntimeError("No se pudo encontrar una asignación válida de grupos.")

    selected: dict[str, list[CaptureGroup]] = {split: [] for split in SPLITS}
    for candidate in best_candidates:
        for group, split_index in zip(candidate.groups, candidate.assignments):
            selected[SPLITS[split_index]].append(group)
    for split in SPLITS:
        selected[split].sort(key=lambda group: group.name)

    group_locations: dict[str, str] = {}
    for split, split_groups in selected.items():
        for group in split_groups:
            if group.name in group_locations:
                raise RuntimeError(f"Fuga de grupo detectada: {group.name}")
            group_locations[group.name] = split
    if len(group_locations) != len(groups):
        raise RuntimeError("La asignación no incluyó todos los grupos.")
    return selected


def _link_or_copy(source: Path, destination: Path) -> str:
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def _split_key(
    source_manifest_sha256: str,
    ratios: dict[str, float],
    seed: int,
) -> tuple[str, dict[str, Any]]:
    selection = {
        "source_manifest_sha256": source_manifest_sha256,
        "ratios": ratios,
        "seed": seed,
        "strategy": "capture_group_source_stratified_balanced_v2",
        "minimum_images_per_source_split": MIN_IMAGES_PER_SOURCE_SPLIT,
    }
    digest = hashlib.sha256(
        json.dumps(selection, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:10]
    return f"group_split_seed_{seed}_{digest}", selection


def _validate_cached_split(
    directory: Path,
    expected_selection: dict[str, Any],
) -> PreparedSplit:
    manifest_path = directory / "split_manifest.json"
    data_yaml = directory / "data.yaml"
    if not manifest_path.is_file() or not data_yaml.is_file():
        raise ValueError(
            f"El split cacheado está incompleto: {directory}. "
            "Use --rebuild-dataset para regenerarlo."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("selection") != expected_selection:
        raise ValueError(f"La selección cacheada no coincide: {manifest_path}")

    all_groups: set[str] = set()
    split_counts: dict[str, int] = {}
    annotation_counts: dict[str, int] = {}
    for split in SPLITS:
        details = manifest.get("splits", {}).get(split, {})
        expected_images = int(details.get("images", -1))
        expected_annotations = int(details.get("annotations", -1))
        image_dir = directory / "images" / split
        label_dir = directory / "labels" / split
        image_paths = sorted(path for path in image_dir.iterdir() if path.is_file())
        label_paths = sorted(label_dir.glob("*.txt"))
        actual_annotations = sum(
            len([line for line in path.read_text().splitlines() if line.strip()])
            for path in label_paths
        )
        if len(image_paths) != expected_images or len(label_paths) != expected_images:
            raise ValueError(f"Cantidad de pares inconsistente en {split}.")
        if actual_annotations != expected_annotations:
            raise ValueError(f"Cantidad de anotaciones inconsistente en {split}.")
        for group in details.get("capture_groups", []):
            if group in all_groups:
                raise ValueError(f"Fuga de grupo en el split cacheado: {group}")
            all_groups.add(group)
        split_counts[split] = expected_images
        annotation_counts[split] = expected_annotations

    return PreparedSplit(
        directory=directory,
        data_yaml=data_yaml,
        manifest=manifest_path,
        split_counts=split_counts,
        annotation_counts=annotation_counts,
    )


def prepare_group_split(
    ratios: dict[str, float],
    seed: int,
    logger: logging.Logger,
    rebuild: bool,
) -> PreparedSplit:
    groups, source_manifest_sha256 = _load_groups()
    selected = assign_groups(groups, ratios, seed)
    directory_name, selection = _split_key(source_manifest_sha256, ratios, seed)
    SPLITS_ROOT.mkdir(parents=True, exist_ok=True)
    target = SPLITS_ROOT / directory_name

    if target.exists() and not rebuild:
        logger.info("Reutilizando split propio validado: %s", target)
        return _validate_cached_split(target, selection)
    if target.exists():
        if target.parent.resolve() != SPLITS_ROOT.resolve():
            raise ValueError(f"Ruta de reconstrucción insegura: {target}")
        logger.warning("Reconstruyendo split existente: %s", target)
        shutil.rmtree(target)

    temporary = Path(tempfile.mkdtemp(prefix=f".{directory_name}_", dir=SPLITS_ROOT))
    materialization: Counter[str] = Counter()
    manifest_splits: dict[str, Any] = {}
    try:
        for split in SPLITS:
            image_dir = temporary / "images" / split
            label_dir = temporary / "labels" / split
            image_dir.mkdir(parents=True)
            label_dir.mkdir(parents=True)
            files: list[str] = []
            source_counts: Counter[str] = Counter()
            annotation_count = 0

            for group in selected[split]:
                for image in group.images:
                    name = str(image["prepared_name"])
                    source_image = NORMALIZED_ROOT / "images" / name
                    source_label = NORMALIZED_ROOT / "labels" / f"{Path(name).stem}.txt"
                    materialization[_link_or_copy(source_image, image_dir / name)] += 1
                    label_method = _link_or_copy(
                        source_label,
                        label_dir / source_label.name,
                    )
                    materialization[label_method] += 1
                    files.append(name)
                    source_counts[group.source] += 1
                    annotation_count += int(image["annotations"])

            manifest_splits[split] = {
                "images": len(files),
                "annotations": annotation_count,
                "capture_groups": [group.name for group in selected[split]],
                "source_counts": dict(sorted(source_counts.items())),
                "files": sorted(files),
            }
            logger.info(
                "Split %-5s: %d imágenes, %d cajas, %d grupos, fuentes=%s",
                split,
                len(files),
                annotation_count,
                len(selected[split]),
                dict(source_counts),
            )

        future_target = target.resolve().as_posix()
        (temporary / "data.yaml").write_text(
            "\n".join(
                [
                    f"path: {json.dumps(future_target)}",
                    "train: images/train",
                    "val: images/val",
                    "test: images/test",
                    "names:",
                    "  0: pod",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        split_manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_dataset": NORMALIZED_ROOT.resolve().as_posix(),
            "selection": selection,
            "class_names": {"0": "pod"},
            "materialization": dict(materialization),
            "splits": manifest_splits,
        }
        write_json(temporary / "split_manifest.json", split_manifest)
        temporary.replace(target)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise

    logger.info("Split propio listo: %s", target)
    return _validate_cached_split(target, selection)


def _metric_comparison(
    baseline: dict[str, Any],
    fine_tuned: dict[str, Any],
) -> dict[str, Any]:
    comparison: dict[str, Any] = {}
    for split in fine_tuned:
        if split not in baseline:
            continue
        comparison[split] = {}
        for metric in ("precision", "recall", "map50", "map75", "map50_95"):
            before = baseline[split].get(metric)
            after = fine_tuned[split].get(metric)
            if isinstance(before, (int, float)) and isinstance(after, (int, float)):
                comparison[split][metric] = {
                    "before": before,
                    "after": after,
                    "delta": after - before,
                }
    return comparison


def _evaluate(
    model: Any,
    data_yaml: Path,
    splits: list[str],
    args: argparse.Namespace,
    device: str,
    workers: int,
    batch: int,
    output_root: Path,
    logger: logging.Logger,
) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for split in splits:
        logger.info("Evaluación explícita sobre %s", split.upper())
        metrics = model.val(
            data=str(data_yaml),
            split=split,
            imgsz=args.imgsz,
            batch=batch,
            workers=workers,
            device=device,
            project=str(output_root),
            name=split,
            exist_ok=True,
            plots=args.plots,
            verbose=True,
        )
        extracted = extract_metrics(metrics)
        payload[split] = extracted
        logger.info(
            "%s -> precision=%s, recall=%s, mAP50=%s, mAP50-95=%s",
            split,
            extracted.get("precision"),
            extracted.get("recall"),
            extracted.get("map50"),
            extracted.get("map50_95"),
        )
    return payload


def main() -> int:
    args = parse_args()
    ratios = validate_args(args)

    if args.prepare_only:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(message)s",
        )
        prepared = prepare_group_split(
            ratios=ratios,
            seed=args.seed,
            logger=logging.getLogger("fine_tune_prepare"),
            rebuild=args.rebuild_dataset,
        )
        print(
            json.dumps(
                {
                    "status": "prepared",
                    "directory": str(prepared.directory),
                    "data_yaml": str(prepared.data_yaml),
                    "split_counts": prepared.split_counts,
                    "annotation_counts": prepared.annotation_counts,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    model_path = args.model.expanduser().resolve()
    if not model_path.is_file():
        raise FileNotFoundError(f"No existe el checkpoint para fine-tuning: {model_path}")

    run_directory = reserve_run_directory(MODELS_ROOT, args.run_name)
    logger = configure_logger(run_directory)
    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    summary: dict[str, Any] = {
        "status": "running",
        "started_at": started_at.isoformat(),
        "run_directory": run_directory,
        "source_checkpoint": model_path,
        "requested_arguments": vars(args),
    }

    logger.info("=" * 72)
    logger.info("FINE-TUNING YOLO26 CON FOTOS PROPIAS")
    logger.info("Directorio de corrida: %s", run_directory)
    logger.info("Checkpoint fuente: %s", model_path)
    logger.info("Python: %s", platform.python_version())
    logger.info("Ejecutable: %s", os.path.realpath(sys.executable))

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
        evaluation_batch = 1 if effective_batch == -1 else max(1, int(effective_batch))

        prepared = prepare_group_split(
            ratios=ratios,
            seed=args.seed,
            logger=logger,
            rebuild=args.rebuild_dataset,
        )
        shutil.copy2(prepared.manifest, run_directory / "split_manifest.json")

        effective_config = {
            "source_checkpoint": model_path,
            "ratios": ratios,
            "split_counts": prepared.split_counts,
            "annotation_counts": prepared.annotation_counts,
            "epochs": args.epochs,
            "image_size": args.imgsz,
            "batch": effective_batch,
            "patience": args.patience,
            "workers": effective_workers,
            "seed": args.seed,
            "device": device,
            "device_description": device_description,
            "freeze_layers": args.freeze,
            "optimizer": OPTIMIZER,
            "learning_rate": args.learning_rate,
            "final_learning_rate_factor": FINAL_LEARNING_RATE_FACTOR,
            "weight_decay": WEIGHT_DECAY,
            "warmup_epochs": WARMUP_EPOCHS,
            "mosaic": MOSAIC,
            "close_mosaic": CLOSE_MOSAIC,
            "cache_images": CACHE_IMAGES,
            "amp": effective_amp,
            "plots": args.plots,
            "deterministic": DETERMINISTIC,
            "minimum_images_per_source_split": MIN_IMAGES_PER_SOURCE_SPLIT,
            "torch_version": torch.__version__,
            "ultralytics_version": ultralytics.__version__,
        }
        write_json(run_directory / "requested_config.json", effective_config)
        logger.info("Dispositivo efectivo: %s", device_description)
        logger.info("Dataset: %s", prepared.data_yaml)
        logger.info("Distribución: %s", prepared.split_counts)
        logger.info("imgsz=%d, batch=%s, freeze=%d", args.imgsz, effective_batch, args.freeze)

        splits_to_evaluate = ["val"]
        if args.test_evaluation:
            splits_to_evaluate.append("test")

        baseline_metrics: dict[str, Any] = {}
        if args.baseline_evaluation:
            logger.info("=" * 72)
            logger.info("LÍNEA BASE DEL MODELO ANTERIOR")
            baseline_model = YOLO(str(model_path))
            baseline_metrics = _evaluate(
                baseline_model,
                prepared.data_yaml,
                splits_to_evaluate,
                args,
                device,
                effective_workers,
                evaluation_batch,
                run_directory / "evaluation_baseline",
                logger,
            )
            write_json(run_directory / "baseline_metrics.json", baseline_metrics)

        logger.info("=" * 72)
        logger.info("CARGA DEL CHECKPOINT PARA FINE-TUNING")
        model = YOLO(str(model_path))
        model_names = getattr(model, "names", {})
        names = list(model_names.values()) if isinstance(model_names, dict) else list(model_names)
        if len(names) != 1 or str(names[0]).lower() not in {"pod", "peanut"}:
            raise ValueError(
                "El checkpoint fuente no parece ser el detector de una clase "
                f"esperado: {model_names}"
            )

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
            "lr0": args.learning_rate,
            "lrf": FINAL_LEARNING_RATE_FACTOR,
            "weight_decay": WEIGHT_DECAY,
            "warmup_epochs": WARMUP_EPOCHS,
            "cos_lr": True,
            "freeze": args.freeze,
            "cache": CACHE_IMAGES,
            "amp": effective_amp,
            "plots": args.plots,
            "mosaic": MOSAIC,
            "close_mosaic": CLOSE_MOSAIC,
            "mixup": 0.0,
            "copy_paste": 0.0,
            "save": True,
            "val": True,
            "verbose": True,
        }
        write_json(run_directory / "train_arguments.json", train_arguments)

        logger.info("=" * 72)
        logger.info("INICIO DEL FINE-TUNING")
        model.train(**train_arguments)
        logger.info("FINE-TUNING FINALIZADO")

        trainer = getattr(model, "trainer", None)
        best_checkpoint = Path(str(getattr(trainer, "best", ""))).resolve()
        last_checkpoint = Path(str(getattr(trainer, "last", ""))).resolve()
        if not best_checkpoint.is_file():
            if last_checkpoint.is_file():
                logger.warning("No se encontró best.pt; se evaluará last.pt.")
                best_checkpoint = last_checkpoint
            else:
                raise FileNotFoundError("El fine-tuning no produjo best.pt ni last.pt.")

        logger.info("=" * 72)
        logger.info("EVALUACIÓN DEL MODELO AJUSTADO")
        evaluation_model = YOLO(str(best_checkpoint))
        fine_tuned_metrics = _evaluate(
            evaluation_model,
            prepared.data_yaml,
            splits_to_evaluate,
            args,
            device,
            effective_workers,
            evaluation_batch,
            run_directory / "evaluation_finetuned",
            logger,
        )
        for split, metrics in fine_tuned_metrics.items():
            write_json(run_directory / f"{split}_metrics.json", metrics)

        comparison = _metric_comparison(baseline_metrics, fine_tuned_metrics)
        if comparison:
            write_json(run_directory / "metrics_comparison.json", comparison)

        summary.update(
            {
                "status": "completed",
                "effective_config": effective_config,
                "dataset": {
                    "directory": prepared.directory,
                    "data_yaml": prepared.data_yaml,
                    "split_counts": prepared.split_counts,
                    "annotation_counts": prepared.annotation_counts,
                },
                "checkpoints": {
                    "source": model_path,
                    "best": best_checkpoint,
                    "last": last_checkpoint,
                },
                "metrics": {
                    "baseline": baseline_metrics,
                    "fine_tuned": fine_tuned_metrics,
                    "comparison": comparison,
                },
            }
        )
        logger.info("Fine-tuning completado correctamente.")
        return 0
    except Exception as error:
        summary.update(
            {
                "status": "failed",
                "error_type": type(error).__name__,
                "error": str(error),
            }
        )
        logger.exception("El pipeline de fine-tuning falló: %s", error)
        raise
    finally:
        summary["finished_at"] = datetime.now(timezone.utc).isoformat()
        summary["duration_seconds"] = round(time.perf_counter() - started_clock, 3)
        write_json(run_directory / "run_summary.json", summary)
        logger.info("Duración total: %.2f segundos", summary["duration_seconds"])
        logger.info("Resumen: %s", run_directory / "run_summary.json")
        logger.info("=" * 72)


if __name__ == "__main__":
    raise SystemExit(main())
