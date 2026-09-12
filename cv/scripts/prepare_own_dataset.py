"""Validate and normalize the locally captured peanut dataset.

The source COCO exports are kept untouched under ``FotosPropias/raw``. This
script creates a flat, deterministic COCO/YOLO view under ``prepared/all``.
It intentionally does not create train/val/test splits: correlated captures
must be split by capture group, not image by image.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image


SCRIPT_DIR = Path(__file__).resolve().parent
CV_ROOT = SCRIPT_DIR.parent
DATASET_ROOT = CV_ROOT / "Datasets" / "FotosPropias"
RAW_ROOT = DATASET_ROOT / "raw"
OUTPUT_ROOT = DATASET_ROOT / "prepared" / "all"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


@dataclass(frozen=True)
class SourceCollection:
    name: str
    prefix: str
    images_dir: Path
    annotations_path: Path


SOURCES = (
    SourceCollection(
        name="photos_session_01",
        prefix="own_photo",
        images_dir=RAW_ROOT / "images" / "photos_session_01",
        annotations_path=(
            RAW_ROOT / "annotations" / "coco" / "photos_session_01.instances.json"
        ),
    ),
    SourceCollection(
        name="video_frames_session_02",
        prefix="own_video",
        images_dir=RAW_ROOT / "images" / "video_frames_session_02",
        annotations_path=(
            RAW_ROOT
            / "annotations"
            / "coco"
            / "video_frames_session_02.instances.json"
        ),
    ),
)

TIME_PATTERN = re.compile(r" at (?P<hour>\d{2})\.(?P<minute>\d{2})\.(?P<second>\d{2})")


def capture_group(collection: str, file_name: str) -> str:
    """Return a conservative group for future leakage-safe splitting."""
    match = TIME_PATTERN.search(file_name)
    if not match:
        raise ValueError(f"No se pudo extraer la hora de captura de {file_name!r}")
    stamp = "".join(match.group(name) for name in ("hour", "minute", "second"))

    if collection == "photos_session_01":
        return f"photos_{stamp}"

    numeric = int(stamp)
    if 34724 <= numeric <= 34726:
        return "video_burst_034724_034726"
    if 34849 <= numeric <= 34851:
        return "video_burst_034849_034851"
    if 35842 <= numeric <= 35845:
        return "video_burst_035842_035845"
    if numeric == 40256:
        return "video_burst_040256"
    raise ValueError(f"No hay un grupo temporal definido para {file_name!r}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def link_or_copy(source: Path, destination: Path) -> str:
    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def validate_bbox(
    annotation: dict[str, Any],
    image: dict[str, Any],
    source_name: str,
) -> tuple[float, float, float, float]:
    bbox = annotation.get("bbox")
    if (
        not isinstance(bbox, list)
        or len(bbox) != 4
        or not all(isinstance(value, (int, float)) for value in bbox)
        or not all(math.isfinite(float(value)) for value in bbox)
    ):
        raise ValueError(
            f"BBox inválida en {source_name}, anotación {annotation.get('id')}: {bbox}"
        )
    x, y, width, height = map(float, bbox)
    image_width = int(image["width"])
    image_height = int(image["height"])
    if width <= 0 or height <= 0:
        raise ValueError(
            f"BBox sin área en {source_name}, anotación {annotation.get('id')}: {bbox}"
        )
    tolerance = 1e-6
    if (
        x < -tolerance
        or y < -tolerance
        or x + width > image_width + tolerance
        or y + height > image_height + tolerance
    ):
        raise ValueError(
            f"BBox fuera de imagen en {source_name}, anotación "
            f"{annotation.get('id')}: {bbox} para {image_width}x{image_height}"
        )
    return x, y, width, height


def prepare() -> dict[str, Any]:
    if OUTPUT_ROOT.exists() and any(OUTPUT_ROOT.iterdir()):
        raise FileExistsError(
            f"La salida ya contiene archivos: {OUTPUT_ROOT}. "
            "Bórrela explícitamente antes de reconstruirla."
        )

    images_output = OUTPUT_ROOT / "images"
    labels_output = OUTPUT_ROOT / "labels"
    annotations_output = OUTPUT_ROOT / "annotations"
    for directory in (images_output, labels_output, annotations_output):
        directory.mkdir(parents=True, exist_ok=True)

    combined_images: list[dict[str, Any]] = []
    combined_annotations: list[dict[str, Any]] = []
    manifest_images: list[dict[str, Any]] = []
    source_stats: dict[str, dict[str, int]] = {}
    transfer_methods: Counter[str] = Counter()
    resolutions: Counter[str] = Counter()
    groups: Counter[str] = Counter()
    hashes: defaultdict[str, list[str]] = defaultdict(list)
    boxes_touching_edge = 0
    small_boxes = 0
    next_image_id = 1
    next_annotation_id = 1

    for source in SOURCES:
        if not source.annotations_path.is_file():
            raise FileNotFoundError(f"Falta el COCO fuente: {source.annotations_path}")
        if not source.images_dir.is_dir():
            raise FileNotFoundError(f"Falta la carpeta de imágenes: {source.images_dir}")

        coco = json.loads(source.annotations_path.read_text(encoding="utf-8"))
        categories = coco.get("categories", [])
        peanut_categories = [item for item in categories if item.get("name") == "peanut"]
        if len(peanut_categories) != 1:
            raise ValueError(
                f"Se esperaba una única categoría 'peanut' en {source.annotations_path}"
            )
        source_category_id = peanut_categories[0]["id"]

        images = coco.get("images", [])
        image_ids = [item.get("id") for item in images]
        if len(image_ids) != len(set(image_ids)):
            raise ValueError(f"Hay IDs de imagen repetidos en {source.annotations_path}")
        images_by_id = {item["id"]: item for item in images}
        annotations_by_image: defaultdict[Any, list[dict[str, Any]]] = defaultdict(list)
        for annotation in coco.get("annotations", []):
            image_id = annotation.get("image_id")
            if image_id not in images_by_id:
                raise ValueError(
                    f"La anotación {annotation.get('id')} referencia una imagen inexistente"
                )
            if annotation.get("category_id") != source_category_id:
                raise ValueError(
                    f"La anotación {annotation.get('id')} no pertenece a 'peanut'"
                )
            annotations_by_image[image_id].append(annotation)

        declared_names = {str(item["file_name"]) for item in images}
        present_names = {
            path.name
            for path in source.images_dir.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        }
        if declared_names != present_names:
            raise ValueError(
                f"COCO e imágenes no coinciden en {source.name}. "
                f"Faltan={sorted(declared_names - present_names)}, "
                f"sobran={sorted(present_names - declared_names)}"
            )

        source_annotation_count = 0
        for source_index, image in enumerate(
            sorted(images, key=lambda item: str(item["file_name"])), start=1
        ):
            original_name = str(image["file_name"])
            original_path = source.images_dir / original_name
            if original_path.stat().st_size == 0:
                raise ValueError(f"La imagen está vacía: {original_path}")
            with Image.open(original_path) as pil_image:
                actual_size = pil_image.size
                pil_image.verify()
            declared_size = (int(image["width"]), int(image["height"]))
            if actual_size != declared_size:
                raise ValueError(
                    f"Dimensiones inconsistentes para {original_path}: "
                    f"COCO={declared_size}, archivo={actual_size}"
                )

            prepared_name = f"{source.prefix}_{source_index:03d}{original_path.suffix.lower()}"
            prepared_path = images_output / prepared_name
            transfer_methods[link_or_copy(original_path, prepared_path)] += 1
            image_hash = sha256(original_path)
            hashes[image_hash].append(prepared_name)
            group = capture_group(source.name, original_name)
            groups[group] += 1
            resolutions[f"{declared_size[0]}x{declared_size[1]}"] += 1

            combined_images.append(
                {
                    "id": next_image_id,
                    "width": declared_size[0],
                    "height": declared_size[1],
                    "file_name": f"images/{prepared_name}",
                    "license": 0,
                    "source_collection": source.name,
                    "capture_group": group,
                    "original_file_name": original_name,
                }
            )

            yolo_lines: list[str] = []
            for annotation in annotations_by_image[image["id"]]:
                x, y, width, height = validate_bbox(annotation, image, source.name)
                image_width, image_height = declared_size
                x_center = (x + width / 2) / image_width
                y_center = (y + height / 2) / image_height
                normalized_width = width / image_width
                normalized_height = height / image_height
                yolo_lines.append(
                    "0 "
                    f"{x_center:.10f} {y_center:.10f} "
                    f"{normalized_width:.10f} {normalized_height:.10f}"
                )

                if (
                    x <= 1
                    or y <= 1
                    or x + width >= image_width - 1
                    or y + height >= image_height - 1
                ):
                    boxes_touching_edge += 1
                if (width * height) / (image_width * image_height) < 0.01:
                    small_boxes += 1

                combined_annotations.append(
                    {
                        "id": next_annotation_id,
                        "image_id": next_image_id,
                        "category_id": 1,
                        "segmentation": annotation.get("segmentation", []),
                        "area": width * height,
                        "bbox": [x, y, width, height],
                        "iscrowd": int(annotation.get("iscrowd", 0)),
                        "attributes": {
                            **annotation.get("attributes", {}),
                            "source_annotation_id": annotation.get("id"),
                        },
                    }
                )
                next_annotation_id += 1
                source_annotation_count += 1

            (labels_output / f"{Path(prepared_name).stem}.txt").write_text(
                "\n".join(yolo_lines) + "\n",
                encoding="utf-8",
            )
            manifest_images.append(
                {
                    "prepared_name": prepared_name,
                    "original_file_name": original_name,
                    "source_collection": source.name,
                    "capture_group": group,
                    "width": declared_size[0],
                    "height": declared_size[1],
                    "annotations": len(yolo_lines),
                    "sha256": image_hash,
                }
            )
            next_image_id += 1

        source_stats[source.name] = {
            "images": len(images),
            "annotations": source_annotation_count,
        }

    duplicate_groups = [names for names in hashes.values() if len(names) > 1]
    if duplicate_groups:
        raise ValueError(f"Se encontraron imágenes duplicadas: {duplicate_groups}")

    combined_coco = {
        "info": {
            "description": "CbaHack own peanut photos, normalized for fine-tuning",
            "version": "1.0",
        },
        "licenses": [{"id": 0, "name": "", "url": ""}],
        "categories": [{"id": 1, "name": "pod", "supercategory": ""}],
        "images": combined_images,
        "annotations": combined_annotations,
    }
    write_json(annotations_output / "instances_all.coco.json", combined_coco)

    manifest = {
        "schema_version": 1,
        "description": "Vista normalizada sin partición train/val/test",
        "class_mapping": {
            "source_coco": {"id": 1, "name": "peanut"},
            "prepared_coco": {"id": 1, "name": "pod"},
            "prepared_yolo": {"id": 0, "name": "pod"},
        },
        "images": manifest_images,
    }
    write_json(OUTPUT_ROOT / "manifest.json", manifest)

    report = {
        "status": "valid",
        "annotation_format_source": "COCO object detection (bbox xywh in pixels)",
        "annotation_format_prepared": "COCO + YOLO detection (normalized xywh)",
        "totals": {
            "images": len(combined_images),
            "annotations": len(combined_annotations),
            "classes": 1,
            "capture_groups": len(groups),
        },
        "by_source": source_stats,
        "capture_groups": dict(sorted(groups.items())),
        "resolutions": dict(sorted(resolutions.items())),
        "quality_checks": {
            "missing_images": 0,
            "extra_images": 0,
            "corrupt_images": 0,
            "dimension_mismatches": 0,
            "invalid_category_references": 0,
            "invalid_image_references": 0,
            "non_positive_boxes": 0,
            "out_of_bounds_boxes": 0,
            "exact_duplicate_images": 0,
            "boxes_touching_image_edge": boxes_touching_edge,
            "boxes_under_one_percent_of_image": small_boxes,
        },
        "image_materialization": dict(transfer_methods),
        "warnings": [
            "No se creó split: las capturas correlacionadas deben mantenerse juntas.",
            "El COCO fuente usa 'peanut'; la vista preparada lo alinea con 'pod'.",
            "Las cajas que tocan un borde son válidas, pero conviene revisar la política para objetos parciales.",
            "Las imágenes provienen de un único entorno y no bastan por sí solas para medir generalización.",
        ],
    }
    write_json(OUTPUT_ROOT / "validation_report.json", report)
    return report


if __name__ == "__main__":
    validation_report = prepare()
    totals = validation_report["totals"]
    print(f"Dataset propio válido: {totals['images']} imágenes, "
          f"{totals['annotations']} cajas, {totals['capture_groups']} grupos.")
    print(f"Salida: {OUTPUT_ROOT}")
