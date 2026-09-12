"""Enviar un JPEG real y verificar inferencia a través de HTTP y WebSocket."""

from __future__ import annotations

import argparse
import asyncio
import json
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import cv2
import numpy as np
import websockets


async def _next_camera_status(viewer, connected: bool) -> None:
    for _ in range(10):
        message = await asyncio.wait_for(viewer.recv(), timeout=30)
        if isinstance(message, str):
            payload = json.loads(message)
            if payload.get("type") == "system_status" and payload.get("camera_connected") is connected:
                return
    raise RuntimeError(f"No se recibió camera_connected={connected}.")


async def _next_jpeg(viewer) -> bytes:
    for _ in range(10):
        message = await asyncio.wait_for(viewer.recv(), timeout=30)
        if isinstance(message, bytes):
            return message
    raise RuntimeError("No se recibió el frame procesado.")


async def run(base_url: str, image_path: Path, output_path: Path | None) -> dict[str, object]:
    parsed = urlparse(base_url.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("--base-url debe ser una URL HTTP completa.")
    websocket_scheme = "wss" if parsed.scheme == "https" else "ws"
    websocket_base = f"{websocket_scheme}://{parsed.netloc}"

    with urllib.request.urlopen(f"{base_url}/healthz", timeout=15) as response:
        health = json.load(response)
    if health != {"status": "ok", "mode": "yolo"}:
        raise RuntimeError(f"La inferencia YOLO no está activa: {health}")

    original = image_path.read_bytes()
    source = cv2.imdecode(np.frombuffer(original, dtype=np.uint8), cv2.IMREAD_COLOR)
    if source is None:
        raise ValueError(f"La imagen de prueba no es un JPEG válido: {image_path}")

    async with websockets.connect(f"{websocket_base}/ws/viewer", max_size=5_000_000) as viewer:
        initial = json.loads(await asyncio.wait_for(viewer.recv(), timeout=15))
        if initial.get("type") != "system_status":
            raise RuntimeError(f"Estado inicial inesperado: {initial}")

        async with websockets.connect(f"{websocket_base}/ws/camera") as camera:
            await _next_camera_status(viewer, True)
            await camera.send(original)
            processed = await _next_jpeg(viewer)
            acknowledgement = json.loads(await asyncio.wait_for(camera.recv(), timeout=30))
            if acknowledgement != {"type": "frame_ack"}:
                raise RuntimeError(f"Confirmación inesperada: {acknowledgement}")

    result = cv2.imdecode(np.frombuffer(processed, dtype=np.uint8), cv2.IMREAD_COLOR)
    if result is None or result.shape != source.shape or processed == original:
        raise RuntimeError("El visor no recibió un JPEG procesado de la misma imagen.")
    if output_path is not None:
        output_path.write_bytes(processed)

    return {
        "status": "ok",
        "mode": health["mode"],
        "source_bytes": len(original),
        "processed_bytes": len(processed),
        "width": source.shape[1],
        "height": source.shape[0],
        "output_path": str(output_path) if output_path else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.base_url, args.image, args.output)), indent=2))


if __name__ == "__main__":
    main()
