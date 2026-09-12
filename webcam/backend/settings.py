"""Configuración del relay de video obtenida desde variables de entorno."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


WEB_ROOT = Path(__file__).resolve().parents[1]


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


settings = Settings()
