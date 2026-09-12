"""Punto de extensión para agregar inferencia YOLO en una etapa posterior."""

from __future__ import annotations

from typing import Protocol


class FrameProcessor(Protocol):
    async def process(self, jpeg: bytes) -> bytes:
        """Procesar un JPEG y devolver el JPEG que recibirán los viewers."""


class PassthroughFrameProcessor:
    """Procesador actual: retransmite el frame sin modificarlo."""

    async def process(self, jpeg: bytes) -> bytes:
        return jpeg

