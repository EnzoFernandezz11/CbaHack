"""Comprobar que el backend entrega un JPEG con las detecciones dibujadas."""

from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from webcam.backend.frame_processor import YoloFrameProcessor


def test_yolo_processor_draws_on_received_jpeg(tmp_path, monkeypatch) -> None:
    model_path = tmp_path / "best.pt"
    model_path.write_bytes(b"checkpoint de prueba")

    class FakeYolo:
        task = "detect"
        names = {0: "pod"}

        def __init__(self, path: str) -> None:
            assert path == str(model_path)

        def predict(self, *, source, imgsz, conf, verbose):
            assert imgsz == 160
            assert conf == 0.3
            assert verbose is False
            annotated = source.copy()
            cv2.rectangle(annotated, (8, 8), (22, 22), (0, 255, 0), -1)
            return [SimpleNamespace(plot=lambda: annotated)]

    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=FakeYolo))
    image = np.zeros((32, 32, 3), dtype=np.uint8)
    success, encoded = cv2.imencode(".jpg", image)
    assert success

    processor = YoloFrameProcessor(model_path, confidence=0.3, image_size=160)
    output = asyncio.run(processor.process(encoded.tobytes()))
    decoded = cv2.imdecode(np.frombuffer(output, dtype=np.uint8), cv2.IMREAD_COLOR)

    assert output.startswith(b"\xff\xd8") and output.endswith(b"\xff\xd9")
    assert decoded is not None
    assert int(decoded[15, 15, 1]) > 180
    assert int(decoded[15, 15, 1]) > int(decoded[15, 15, 0]) * 2


def test_yolo_processor_rejects_missing_checkpoint(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="checkpoint YOLO"):
        YoloFrameProcessor(tmp_path / "missing.pt")
