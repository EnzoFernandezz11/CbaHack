"""Create leakage-safe COCO train/val/test splits grouped by source capture."""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SOURCE_SPLITS = ("train", "valid", "val", "test")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
GROUP_PATTERN = re.compile(r"^(?P<group>.+?)_jpg\.rf\.[^.]+\.(?:jpg|jpeg|png)$", re.IGNORECASE)


@dataclass(frozen=True)
class ImageRecord:
    source_path: Path
    source_split: str
    group: str
    image: dict[str, Any]
    annotations: tuple[dict[str, Any], ...]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Combine the COCO splits exported by Roboflow and create a new "
            "70/15/15 split without placing variants of one capture in "
            "different partitions."
        )
    )
    parser.add_argument("source", type=Path, help="Roboflow COCO dataset directory")
    parser.add_argument("output", type=Path, help="New dataset directory")
    parser.add_argument(
        "--materialization",
        choices=("hardlink", "copy"),
        default="hardlink",
        help="How to materialize images (default: hardlink, with copy fallback)",
    )
    return parser.parse_args()


def capture_group(file_name: str) -> str:
    match = GROUP_PATTERN.match(Path(file_name).name)
    if not match:
        raise ValueError(
            f"Cannot infer the source capture from {file_name!r}; expected a "
            "Roboflow name such as CAPTURE_jpg.rf.HASH.jpg"
        )
    return match.group("group")


def load_records(source: Path) -> tuple[list[ImageRecord], dict[str, Any]]:
    records: list[ImageRecord] = []
    metadata: dict[str, Any] | None = None
    seen_file_names: set[str] = set()
    loaded_splits = 0

    for split in SOURCE_SPLITS:
        split_dir = source / split
        annotation_path = split_dir / "_annotations.coco.json"
        if not annotation_path.is_file():
            continue

        loaded_splits += 1
        coco = json.loads(annotation_path.read_text(encoding="utf-8"))
        current_metadata = {
            "info": coco.get("info", {}),
            "licenses": coco.get("licenses", []),
            "categories": coco.get("categories", []),
        }
        if metadata is None:
            metadata = current_metadata
        elif current_metadata["categories"] != metadata["categories"]:
            raise ValueError(f"COCO categories differ in source split {split!r}")

        images_by_id = {image["id"]: image for image in coco.get("images", [])}
        annotations_by_image: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for annotation in coco.get("annotations", []):
            image_id = annotation["image_id"]
            if image_id not in images_by_id:
                raise ValueError(
                    f"Annotation {annotation.get('id')} in {split!r} references "
                    f"missing image ID {image_id}"
                )
            annotations_by_image[image_id].append(annotation)

        for image in coco.get("images", []):
            file_name = Path(image["file_name"]).name
            if Path(file_name).suffix.lower() not in IMAGE_EXTENSIONS:
                raise ValueError(f"Unsupported image extension in {file_name!r}")
            if file_name in seen_file_names:
                raise ValueError(f"Duplicate image filename across source splits: {file_name}")

            source_path = split_dir / file_name
            if not source_path.is_file():
                raise FileNotFoundError(f"COCO image does not exist: {source_path}")

            seen_file_names.add(file_name)
            normalized_image = dict(image)
            normalized_image["file_name"] = file_name
            records.append(
                ImageRecord(
                    source_path=source_path,
                    source_split=split,
                    group=capture_group(file_name),
                    image=normalized_image,
                    annotations=tuple(annotations_by_image.get(image["id"], [])),
                )
            )

    if loaded_splits == 0 or metadata is None:
        raise FileNotFoundError(f"No COCO split was found under {source}")
    if not records:
        raise ValueError("The source COCO files contain no images")

    return records, metadata


def split_stats(groups: dict[str, list[ImageRecord]], names: tuple[str, ...]) -> tuple[int, int]:
    images = sum(len(groups[name]) for name in names)
    annotations = sum(
        len(record.annotations)
        for name in names
        for record in groups[name]
    )
    return images, annotations


def choose_groups(records: list[ImageRecord]) -> dict[str, tuple[str, ...]]:
    groups: dict[str, list[ImageRecord]] = defaultdict(list)
    for record in records:
        groups[record.group].append(record)

    group_names = tuple(sorted(groups))
    group_count = len(group_names)
    val_count = round(group_count * 0.15)
    test_count = round(group_count * 0.15)
    train_count = group_count - val_count - test_count
    if min(train_count, val_count, test_count) < 1:
        raise ValueError(
            f"At least one capture per split is required; only {group_count} groups were found"
        )

    total_images = len(records)
    total_annotations = sum(len(record.annotations) for record in records)
    targets = {
        "train": (total_images * 0.70, total_annotations * 0.70),
        "val": (total_images * 0.15, total_annotations * 0.15),
        "test": (total_images * 0.15, total_annotations * 0.15),
    }

    stats_cache: dict[tuple[str, ...], tuple[int, int]] = {}

    def stats(names: tuple[str, ...]) -> tuple[int, int]:
        if names not in stats_cache:
            stats_cache[names] = split_stats(groups, names)
        return stats_cache[names]

    def relative_error(split: str, names: tuple[str, ...]) -> float:
        images, annotations = stats(names)
        target_images, target_annotations = targets[split]
        return (
            ((images - target_images) / target_images) ** 2
            + ((annotations - target_annotations) / target_annotations) ** 2
        )

    best_key: tuple[Any, ...] | None = None
    best_assignment: dict[str, tuple[str, ...]] | None = None

    for val_groups in itertools.combinations(group_names, val_count):
        remaining_after_val = tuple(name for name in group_names if name not in val_groups)
        for test_groups in itertools.combinations(remaining_after_val, test_count):
            train_groups = tuple(
                name
                for name in remaining_after_val
                if name not in test_groups
            )
            score = (
                relative_error("train", train_groups)
                + relative_error("val", val_groups)
                + relative_error("test", test_groups)
            )
            key = (round(score, 15), val_groups, test_groups)
            if best_key is None or key < best_key:
                best_key = key
                best_assignment = {
                    "train": train_groups,
                    "val": val_groups,
                    "test": test_groups,
                }

    if best_assignment is None:
        raise RuntimeError("Could not generate a grouped split")
    return best_assignment


def materialize_image(source: Path, destination: Path, mode: str) -> str:
    if mode == "copy":
        shutil.copy2(source, destination)
        return "copy"

    try:
        os.link(source, destination)
        return "hardlink"
    except OSError:
        shutil.copy2(source, destination)
        return "copy_fallback"


def write_dataset(
    source: Path,
    output: Path,
    records: list[ImageRecord],
    metadata: dict[str, Any],
    assignment: dict[str, tuple[str, ...]],
    materialization: str,
) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(
            f"Output already exists: {output}. Remove it explicitly before regenerating."
        )

    output.mkdir(parents=True)
    records_by_group: dict[str, list[ImageRecord]] = defaultdict(list)
    for record in records:
        records_by_group[record.group].append(record)

    manifest: dict[str, Any] = {
        "source": Path(os.path.relpath(source, output)).as_posix(),
        "strategy": "grouped_by_capture_and_balanced_by_images_and_annotations",
        "target_ratios": {"train": 0.70, "val": 0.15, "test": 0.15},
        "group_pattern": GROUP_PATTERN.pattern,
        "splits": {},
        "materialization": defaultdict(int),
    }

    next_annotation_id = 0
    for split in ("train", "val", "test"):
        split_dir = output / split
        split_dir.mkdir()
        selected_records = sorted(
            (
                record
                for group in assignment[split]
                for record in records_by_group[group]
            ),
            key=lambda record: record.image["file_name"],
        )

        output_images: list[dict[str, Any]] = []
        output_annotations: list[dict[str, Any]] = []
        for new_image_id, record in enumerate(selected_records):
            file_name = record.image["file_name"]
            method = materialize_image(
                record.source_path,
                split_dir / file_name,
                materialization,
            )
            manifest["materialization"][method] += 1

            image = dict(record.image)
            image["id"] = new_image_id
            output_images.append(image)

            for source_annotation in record.annotations:
                annotation = dict(source_annotation)
                annotation["id"] = next_annotation_id
                annotation["image_id"] = new_image_id
                output_annotations.append(annotation)
                next_annotation_id += 1

        coco = {
            "info": metadata["info"],
            "licenses": metadata["licenses"],
            "categories": metadata["categories"],
            "images": output_images,
            "annotations": output_annotations,
        }
        (split_dir / "_annotations.coco.json").write_text(
            json.dumps(coco, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest["splits"][split] = {
            "groups": list(assignment[split]),
            "group_count": len(assignment[split]),
            "images": len(output_images),
            "annotations": len(output_annotations),
        }

    manifest["materialization"] = dict(manifest["materialization"])
    (output / "split_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Dataset reorganizado",
        "",
        "División COCO 70/15/15 agrupada por captura base para impedir que parches o",
        "augmentations de una misma captura aparezcan en más de una partición.",
        "",
        "| Split | Capturas base | Imágenes | Anotaciones |",
        "| --- | ---: | ---: | ---: |",
    ]
    for split in ("train", "val", "test"):
        details = manifest["splits"][split]
        lines.append(
            f"| `{split}` | {details['group_count']} | {details['images']} | "
            f"{details['annotations']} |"
        )
    lines.extend(
        [
            "",
            "La asignación exacta y la estrategia utilizada están registradas en",
            "`split_manifest.json`. Los archivos `_annotations.coco.json` fueron",
            "regenerados con IDs consistentes para cada split.",
            "",
            "La descarga original no fue modificada.",
            "",
            "> Nota: la versión descargada ya contiene augmentations. Esta división agrupada",
            "> es la alternativa más segura con los archivos disponibles. Para una evaluación",
            "> más rigurosa, se deben dividir primero las imágenes originales por captura y",
            "> aplicar augmentations únicamente a `train`, no a `val` ni a `test`.",
            "",
        ]
    )
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")
    return manifest


def validate_manifest(manifest: dict[str, Any], record_count: int, annotation_count: int) -> None:
    split_groups = [
        set(manifest["splits"][split]["groups"])
        for split in ("train", "val", "test")
    ]
    if any(left & right for left, right in itertools.combinations(split_groups, 2)):
        raise RuntimeError("Capture leakage detected after splitting")

    output_images = sum(details["images"] for details in manifest["splits"].values())
    output_annotations = sum(
        details["annotations"] for details in manifest["splits"].values()
    )
    if output_images != record_count or output_annotations != annotation_count:
        raise RuntimeError("Output totals differ from source totals")


def main() -> None:
    args = parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    if not source.is_dir():
        raise NotADirectoryError(source)
    if source == output or source in output.parents:
        raise ValueError("Output must be outside the immutable source dataset")

    records, metadata = load_records(source)
    assignment = choose_groups(records)
    annotation_count = sum(len(record.annotations) for record in records)
    manifest = write_dataset(
        source,
        output,
        records,
        metadata,
        assignment,
        args.materialization,
    )
    validate_manifest(manifest, len(records), annotation_count)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
