"""Prepare a deterministic COCO subset in Ultralytics YOLO detection format."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import os
import random
import re
import shutil
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SPLITS = ("train", "val", "test")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
CAPTURE_PATTERN = re.compile(
    r"^(?P<capture>.+?)_jpg\.rf\.[^.]+\.(?:jpg|jpeg|png)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SourceImage:
    split: str
    capture: str
    path: Path
    file_name: str
    width: int
    height: int
    annotations: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class PreparedDataset:
    directory: Path
    data_yaml: Path
    manifest: Path
    total_images: int
    split_counts: dict[str, int]


class EmptyBoundingBoxError(ValueError):
    """A COCO box that has no usable area after validation or clipping."""


def _capture_name(file_name: str) -> str:
    match = CAPTURE_PATTERN.match(Path(file_name).name)
    if not match:
        raise ValueError(
            f"No se pudo identificar la captura base de {file_name!r}. "
            "Se esperaba el patrón CAPTURA_jpg.rf.HASH.jpg."
        )
    return match.group("capture")


def _conventional_round(value: float) -> int:
    """Round positive values to nearest integer, with halves rounded upward."""
    return int(math.floor(value + 0.5))


def allocate_split_counts(
    total: int,
    ratios: dict[str, float],
) -> dict[str, int]:
    if total < len(SPLITS):
        raise ValueError(
            f"El subset debe contener al menos {len(SPLITS)} imágenes para que "
            "train, val y test no queden vacíos."
        )

    if set(ratios) != set(SPLITS):
        raise ValueError(f"Los ratios deben definir exactamente: {', '.join(SPLITS)}")
    if any(not math.isfinite(value) or value <= 0 for value in ratios.values()):
        raise ValueError("Todos los ratios deben ser números positivos y finitos.")
    if not math.isclose(sum(ratios.values()), 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError(
            f"TRAIN_RATIO + VAL_RATIO + TEST_RATIO debe sumar 1.0; "
            f"suma actual: {sum(ratios.values()):.12f}"
        )

    raw = {split: total * ratios[split] for split in SPLITS}
    counts = {split: math.floor(raw[split]) for split in SPLITS}
    remaining = total - sum(counts.values())
    priority = {split: index for index, split in enumerate(SPLITS)}
    order = sorted(
        SPLITS,
        key=lambda split: (-(raw[split] - counts[split]), priority[split]),
    )
    for split in order[:remaining]:
        counts[split] += 1

    empty_splits = [split for split in SPLITS if counts[split] == 0]
    if empty_splits:
        raise ValueError(
            "El porcentaje solicitado deja splits vacíos: " + ", ".join(empty_splits)
        )
    return counts


def _load_source_dataset(
    source: Path,
    logger: logging.Logger,
) -> tuple[dict[str, list[SourceImage]], int]:
    source = source.resolve()
    records: dict[str, list[SourceImage]] = {split: [] for split in SPLITS}
    capture_locations: dict[str, str] = {}
    category_id: int | None = None
    seen_files: set[str] = set()

    for split in SPLITS:
        split_dir = source / split
        annotation_path = split_dir / "_annotations.coco.json"
        if not annotation_path.is_file():
            raise FileNotFoundError(f"Falta el archivo COCO: {annotation_path}")

        logger.info("Leyendo anotaciones COCO de %s", annotation_path)
        coco = json.loads(annotation_path.read_text(encoding="utf-8"))
        pod_categories = [
            item for item in coco.get("categories", []) if item.get("name") == "pod"
        ]
        if len(pod_categories) != 1:
            raise ValueError(
                f"Se esperaba una categoría efectiva llamada 'pod' en {annotation_path}"
            )
        current_category_id = int(pod_categories[0]["id"])
        if category_id is None:
            category_id = current_category_id
        elif category_id != current_category_id:
            raise ValueError("El ID de la categoría 'pod' cambia entre splits COCO.")

        images_by_id = {item["id"]: item for item in coco.get("images", [])}
        annotations_by_image: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for annotation in coco.get("annotations", []):
            if annotation.get("image_id") not in images_by_id:
                raise ValueError(
                    f"La anotación {annotation.get('id')} referencia una imagen inexistente."
                )
            if int(annotation.get("category_id", -1)) != current_category_id:
                raise ValueError(
                    f"La anotación {annotation.get('id')} usa una clase distinta de 'pod'."
                )
            annotations_by_image[annotation["image_id"]].append(annotation)

        for image in coco.get("images", []):
            file_name = Path(str(image["file_name"])).name
            if Path(file_name).suffix.lower() not in IMAGE_EXTENSIONS:
                raise ValueError(f"Extensión de imagen no soportada: {file_name}")
            if file_name in seen_files:
                raise ValueError(f"Nombre de imagen duplicado en el dataset: {file_name}")
            seen_files.add(file_name)

            image_path = split_dir / file_name
            if not image_path.is_file():
                raise FileNotFoundError(f"La imagen declarada en COCO no existe: {image_path}")
            if image_path.stat().st_size == 0:
                raise ValueError(f"La imagen está vacía: {image_path}")

            width = int(image["width"])
            height = int(image["height"])
            if width <= 0 or height <= 0:
                raise ValueError(f"Dimensiones inválidas para {file_name}: {width}x{height}")

            capture = _capture_name(file_name)
            previous_split = capture_locations.get(capture)
            if previous_split is not None and previous_split != split:
                raise ValueError(
                    f"Data leakage detectado: la captura {capture!r} aparece en "
                    f"{previous_split!r} y {split!r}."
                )
            capture_locations[capture] = split
            records[split].append(
                SourceImage(
                    split=split,
                    capture=capture,
                    path=image_path,
                    file_name=file_name,
                    width=width,
                    height=height,
                    annotations=tuple(annotations_by_image.get(image["id"], [])),
                )
            )

        logger.info(
            "Split fuente %-5s: %d imágenes, %d anotaciones, %d capturas base",
            split,
            len(records[split]),
            sum(len(item.annotations) for item in records[split]),
            len({item.capture for item in records[split]}),
        )

    if category_id is None:
        raise ValueError("No se encontró la categoría 'pod'.")
    return records, category_id


def _balanced_sample(
    records: list[SourceImage],
    count: int,
    seed: int,
    split: str,
) -> list[SourceImage]:
    if count > len(records):
        raise ValueError(
            f"El split {split!r} necesita {count} imágenes, pero solo dispone de {len(records)}."
        )
    if count == len(records):
        return sorted(records, key=lambda item: item.file_name)

    grouped: dict[str, list[SourceImage]] = defaultdict(list)
    for record in records:
        grouped[record.capture].append(record)

    group_names = sorted(grouped)
    random.Random(f"{seed}:{split}:capture-order").shuffle(group_names)
    for capture in group_names:
        grouped[capture].sort(key=lambda item: item.file_name)
        random.Random(f"{seed}:{split}:{capture}:images").shuffle(grouped[capture])

    selected: list[SourceImage] = []
    offsets = {capture: 0 for capture in group_names}
    while len(selected) < count:
        made_progress = False
        for capture in group_names:
            offset = offsets[capture]
            candidates = grouped[capture]
            if offset >= len(candidates):
                continue
            selected.append(candidates[offset])
            offsets[capture] += 1
            made_progress = True
            if len(selected) == count:
                break
        if not made_progress:
            raise RuntimeError(f"No se pudo completar el muestreo del split {split!r}.")

    return sorted(selected, key=lambda item: item.file_name)


def _hardlink_or_copy(source: Path, destination: Path) -> str:
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def _annotation_to_yolo(
    annotation: dict[str, Any],
    image: SourceImage,
) -> tuple[str, bool]:
    bbox = annotation.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise ValueError(
            f"Bounding box COCO inválida en la anotación {annotation.get('id')}."
        )
    x, y, width, height = (float(value) for value in bbox)
    if not all(math.isfinite(value) for value in (x, y, width, height)):
        raise ValueError(f"Bounding box no finita en la anotación {annotation.get('id')}.")
    if width <= 0 or height <= 0:
        raise EmptyBoundingBoxError(
            f"Bounding box sin área en la anotación {annotation.get('id')}."
        )

    x1 = max(0.0, x)
    y1 = max(0.0, y)
    x2 = min(float(image.width), x + width)
    y2 = min(float(image.height), y + height)
    clipped = not all(
        math.isclose(left, right, rel_tol=0.0, abs_tol=1e-9)
        for left, right in ((x1, x), (y1, y), (x2, x + width), (y2, y + height))
    )
    if x2 <= x1 or y2 <= y1:
        raise EmptyBoundingBoxError(
            f"Bounding box fuera de la imagen en la anotación {annotation.get('id')}."
        )

    center_x = ((x1 + x2) / 2.0) / image.width
    center_y = ((y1 + y2) / 2.0) / image.height
    normalized_width = (x2 - x1) / image.width
    normalized_height = (y2 - y1) / image.height
    values = (center_x, center_y, normalized_width, normalized_height)
    if any(value < 0.0 or value > 1.0 for value in values):
        raise ValueError(
            f"Conversión YOLO fuera de rango para la anotación {annotation.get('id')}."
        )
    return "0 " + " ".join(f"{value:.8f}" for value in values), clipped


def _configuration_key(
    source_total: int,
    selected_total: int,
    dataset_percent: float,
    ratios: dict[str, float],
    seed: int,
) -> tuple[str, dict[str, Any]]:
    payload = {
        "source_total": source_total,
        "selected_total": selected_total,
        "dataset_percent": dataset_percent,
        "ratios": ratios,
        "seed": seed,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:10]
    percent_text = f"{dataset_percent:.8f}".rstrip("0").rstrip(".").replace(".", "p")
    return f"subset_{selected_total}_pct_{percent_text}_seed_{seed}_{digest}", payload


def _validate_existing_output(
    directory: Path,
    expected_payload: dict[str, Any],
) -> PreparedDataset:
    manifest_path = directory / "subset_manifest.json"
    data_yaml = directory / "data.yaml"
    if not manifest_path.is_file() or not data_yaml.is_file():
        raise ValueError(
            f"El dataset preparado existente está incompleto: {directory}. "
            "Use --rebuild-dataset para regenerarlo."
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("selection") != expected_payload:
        raise ValueError(
            f"El manifiesto existente no coincide con la configuración: {manifest_path}"
        )

    split_counts: dict[str, int] = {}
    for split in SPLITS:
        details = manifest.get("splits", {}).get(split, {})
        expected_count = int(details.get("images", -1))
        image_dir = directory / "images" / split
        label_dir = directory / "labels" / split
        image_count = len(
            [path for path in image_dir.iterdir() if path.suffix.lower() in IMAGE_EXTENSIONS]
        )
        label_count = len(list(label_dir.glob("*.txt")))
        if image_count != expected_count or label_count != expected_count:
            raise ValueError(
                f"El subset cacheado está incompleto en {split}: "
                f"manifest={expected_count}, images={image_count}, labels={label_count}."
            )
        split_counts[split] = expected_count

    return PreparedDataset(
        directory=directory,
        data_yaml=data_yaml,
        manifest=manifest_path,
        total_images=sum(split_counts.values()),
        split_counts=split_counts,
    )


def prepare_yolo_dataset(
    source: Path,
    output_root: Path,
    dataset_percent: float,
    ratios: dict[str, float],
    seed: int,
    logger: logging.Logger | None = None,
    rebuild: bool = False,
) -> PreparedDataset:
    logger = logger or logging.getLogger("prepare_yolo_dataset")
    source = source.resolve()
    output_root = output_root.resolve()
    if not source.is_dir():
        raise NotADirectoryError(f"No existe el dataset COCO fuente: {source}")
    if not math.isfinite(dataset_percent) or dataset_percent <= 0 or dataset_percent > 100:
        raise ValueError("DATASET_PERCENT debe ser mayor que 0 y menor o igual que 100.")

    logger.info("=" * 72)
    logger.info("PREPARACIÓN DEL DATASET YOLO")
    logger.info("Fuente COCO: %s", source)
    logger.info("Porcentaje solicitado: %.8g%%", dataset_percent)
    logger.info("Ratios: %s", ", ".join(f"{key}={ratios[key]:.2%}" for key in SPLITS))
    logger.info("Semilla: %d", seed)

    source_records, pod_category_id = _load_source_dataset(source, logger)
    source_total = sum(len(items) for items in source_records.values())
    selected_total = _conventional_round(source_total * dataset_percent / 100.0)
    selected_total = max(1, min(source_total, selected_total))
    split_counts = allocate_split_counts(selected_total, ratios)
    for split in SPLITS:
        if split_counts[split] > len(source_records[split]):
            raise ValueError(
                f"El ratio solicita {split_counts[split]} imágenes para {split}, "
                f"pero ese split fuente solo contiene {len(source_records[split])}."
            )

    directory_name, selection_payload = _configuration_key(
        source_total,
        selected_total,
        dataset_percent,
        ratios,
        seed,
    )
    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / directory_name

    if target.exists() and not rebuild:
        logger.info("Reutilizando subset ya preparado: %s", target)
        prepared = _validate_existing_output(target, selection_payload)
        logger.info("Dataset cacheado validado correctamente.")
        return prepared
    if target.exists():
        if target.parent.resolve() != output_root:
            raise ValueError(f"Ruta de regeneración insegura: {target}")
        logger.warning("Regenerando subset existente: %s", target)
        shutil.rmtree(target)

    selected: dict[str, list[SourceImage]] = {}
    for split in SPLITS:
        selected[split] = _balanced_sample(
            source_records[split],
            split_counts[split],
            seed,
            split,
        )
        logger.info(
            "Subset %-5s: %d imágenes de %d capturas, %d anotaciones",
            split,
            len(selected[split]),
            len({item.capture for item in selected[split]}),
            sum(len(item.annotations) for item in selected[split]),
        )

    temporary = Path(tempfile.mkdtemp(prefix=f".{directory_name}_", dir=output_root))
    materialization: dict[str, int] = defaultdict(int)
    clipped_boxes = 0
    skipped_invalid_annotations: list[dict[str, Any]] = []
    manifest_splits: dict[str, Any] = {}
    try:
        for split in SPLITS:
            image_dir = temporary / "images" / split
            label_dir = temporary / "labels" / split
            image_dir.mkdir(parents=True)
            label_dir.mkdir(parents=True)

            annotation_count = 0
            for image in selected[split]:
                method = _hardlink_or_copy(image.path, image_dir / image.file_name)
                materialization[method] += 1
                label_lines: list[str] = []
                for annotation in image.annotations:
                    if int(annotation["category_id"]) != pod_category_id:
                        raise ValueError("Se encontró una clase no esperada durante la conversión.")
                    try:
                        line, clipped = _annotation_to_yolo(annotation, image)
                    except EmptyBoundingBoxError as error:
                        skipped_invalid_annotations.append(
                            {
                                "split": split,
                                "annotation_id": annotation.get("id"),
                                "image": image.file_name,
                                "bbox": annotation.get("bbox"),
                                "reason": str(error),
                            }
                        )
                        logger.warning(
                            "Omitiendo anotación COCO inválida %s en %s: %s",
                            annotation.get("id"),
                            image.file_name,
                            error,
                        )
                        continue
                    label_lines.append(line)
                    clipped_boxes += int(clipped)
                annotation_count += len(label_lines)
                (label_dir / f"{Path(image.file_name).stem}.txt").write_text(
                    "\n".join(label_lines) + ("\n" if label_lines else ""),
                    encoding="utf-8",
                )

            manifest_splits[split] = {
                "images": len(selected[split]),
                "annotations": annotation_count,
                "captures": sorted({item.capture for item in selected[split]}),
                "files": [item.file_name for item in selected[split]],
            }

        data_yaml = temporary / "data.yaml"
        future_target = target.resolve().as_posix()
        data_yaml.write_text(
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

        manifest = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_dataset": source.as_posix(),
            "selection": selection_payload,
            "strategy": "deterministic_balanced_sampling_within_leakage_safe_splits",
            "class_mapping": {str(pod_category_id): 0},
            "class_names": {"0": "pod"},
            "materialization": dict(materialization),
            "clipped_boxes": clipped_boxes,
            "skipped_invalid_annotations": skipped_invalid_annotations,
            "splits": manifest_splits,
        }
        (temporary / "subset_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(target)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise

    prepared = _validate_existing_output(target, selection_payload)
    logger.info("Materialización: %s", dict(materialization))
    logger.info("Bounding boxes recortadas a los límites de imagen: %d", clipped_boxes)
    logger.info(
        "Anotaciones inválidas omitidas y registradas: %d",
        len(skipped_invalid_annotations),
    )
    logger.info("Dataset YOLO listo: %s", target)
    logger.info("Archivo de configuración: %s", prepared.data_yaml)
    logger.info("=" * 72)
    return prepared


def _parse_args() -> argparse.Namespace:
    cv_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=cv_root / "Datasets" / "peanut_tifton_patch_v4_grouped",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=cv_root / "Datasets" / "yolo26_working",
    )
    parser.add_argument("--dataset-percent", type=float, default=100.0)
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rebuild-dataset", action="store_true")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
    )
    args = _parse_args()
    result = prepare_yolo_dataset(
        source=args.source,
        output_root=args.output_root,
        dataset_percent=args.dataset_percent,
        ratios={
            "train": args.train_ratio,
            "val": args.val_ratio,
            "test": args.test_ratio,
        },
        seed=args.seed,
        logger=logging.getLogger("prepare_yolo_dataset"),
        rebuild=args.rebuild_dataset,
    )
    print(
        json.dumps(
            {
                "directory": str(result.directory),
                "data_yaml": str(result.data_yaml),
                "manifest": str(result.manifest),
                "total_images": result.total_images,
                "split_counts": result.split_counts,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
