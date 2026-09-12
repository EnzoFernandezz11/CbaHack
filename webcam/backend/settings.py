"""Configuración del relay de video obtenida desde variables de entorno."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parents[1]


def _model_path() -> Path | None:
    raw_value = os.getenv("WEB_MODEL_PATH", "").strip()
    if not raw_value:
        return None
    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = WEB_ROOT.parent / path
    return path.resolve()


def _confidence() -> float:
    raw_value = os.getenv("WEB_MODEL_CONFIDENCE", "0.25")
    try:
        value = float(raw_value)
    except ValueError as error:
        raise ValueError("WEB_MODEL_CONFIDENCE debe ser un número.") from error
    if not 0 < value <= 1:
        raise ValueError("WEB_MODEL_CONFIDENCE debe estar entre 0 y 1.")
    return value


def _positive_integer(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} debe ser un número entero; valor recibido: {raw_value!r}") from error
    if value <= 0:
        raise ValueError(f"{name} debe ser mayor que cero; valor recibido: {value}")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """Valores ajustables sin modificar el código."""

    frontend_directory: Path = WEB_ROOT / "frontend"
    maximum_frame_bytes: int = _positive_integer("WEB_MAX_FRAME_BYTES", 2_500_000)
    model_path: Path | None = _model_path()
    model_confidence: float = _confidence()
    model_image_size: int = _positive_integer("WEB_MODEL_IMAGE_SIZE", 640)


settings = Settings()
