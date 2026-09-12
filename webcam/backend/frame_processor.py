"""Procesadores de frames para el relay y la inferencia YOLO."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol


class FrameProcessor(Protocol):
    async def process(self, jpeg: bytes) -> bytes:
        """Procesar un JPEG y devolver el JPEG que recibirán los viewers."""


class PassthroughFrameProcessor:
    """Procesador actual: retransmite el frame sin modificarlo."""

    async def process(self, jpeg: bytes) -> bytes:
        return jpeg


class YoloFrameProcessor:
    """Carga un detector una vez y dibuja sus detecciones sobre cada JPEG."""

    def __init__(self, model_path: Path, confidence: float = 0.25, image_size: int = 640):
        if not model_path.is_file():
            raise FileNotFoundError(f"No existe el checkpoint YOLO: {model_path}")

        import cv2
        import numpy as np
        from ultralytics import YOLO

        self._cv2 = cv2
        self._np = np
        self._model = YOLO(str(model_path))
        if self._model.task != "detect":
            raise ValueError(f"El checkpoint debe ser de detección; tarea: {self._model.task}")
        self.confidence = confidence
        self.image_size = image_size
        self.names = self._model.names

    async def process(self, jpeg: bytes) -> bytes:
        # La inferencia en CPU puede tardar; no bloquear el event loop de WebSocket.
        return await asyncio.to_thread(self._process_sync, jpeg)

    def _process_sync(self, jpeg: bytes) -> bytes:
        frame = self._cv2.imdecode(
            self._np.frombuffer(jpeg, dtype=self._np.uint8),
            self._cv2.IMREAD_COLOR,
        )
        if frame is None:
            raise ValueError("El frame recibido no se pudo decodificar como JPEG.")

        result = self._model.predict(
            source=frame,
            imgsz=self.image_size,
            conf=self.confidence,
            verbose=False,
        )[0]
        encoded, output = self._cv2.imencode(
            ".jpg",
            result.plot(),
            [self._cv2.IMWRITE_JPEG_QUALITY, 80],
        )
        if not encoded:
            raise RuntimeError("No se pudo codificar el frame procesado como JPEG.")
        return output.tobytes()
