"""Pruebas del contrato de procesamiento y smoke opcional del checkpoint real."""

from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from pathlib import Path

import pytest

from backend.frame_processor import PassthroughFrameProcessor, YoloFrameProcessor
from backend.settings import REPOSITORY_ROOT, settings


def test_passthrough_preserves_the_jpeg_and_reports_no_detections() -> None:
    jpeg = b"\xff\xd8unchanged\xff\xd9"
    result = asyncio.run(PassthroughFrameProcessor().process(jpeg))

    assert result.jpeg == jpeg
    assert result.detection_count == 0
    assert result.average_confidence is None
    assert result.inference_ms == 0.0


@pytest.mark.yolo
def test_real_checkpoint_processes_an_own_photo() -> None:
    if os.getenv("RUN_YOLO_INTEGRATION") != "1":
        pytest.skip("Defina RUN_YOLO_INTEGRATION=1 para probar el checkpoint real.")

    source = (
        REPOSITORY_ROOT
        / "cv"
        / "Datasets"
        / "FotosPropias"
        / "prepared"
        / "all"
        / "images"
        / "own_photo_001.jpeg"
    )
    if not source.is_file():
        pytest.skip(f"No está disponible la imagen de integración: {source}")

    processor = YoloFrameProcessor(
        replace(settings, processor_mode="yolo", yolo_device="auto", yolo_image_size=640)
    )
    result = asyncio.run(processor.process(Path(source).read_bytes()))

    assert result.jpeg.startswith(b"\xff\xd8")
    assert result.jpeg.endswith(b"\xff\xd9")
    assert result.processing_ms >= result.inference_ms > 0
    assert result.detection_count >= 0
    assert processor.status()["model_ready"] is True
