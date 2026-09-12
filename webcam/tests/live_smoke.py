"""Comprobar HTTP y WebSocket contra un servidor Uvicorn ya iniciado."""

from __future__ import annotations

import argparse
import asyncio
import json
import urllib.request
from urllib.parse import urlparse

import websockets


JPEG_FRAME = b"\xff\xd8live-smoke-frame\xff\xd9"


def _read_json(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 - URL local explícita
        if response.status != 200:
            raise RuntimeError(f"{url} respondió HTTP {response.status}")
        return json.loads(response.read())


async def run(base_url: str) -> dict[str, object]:
    parsed = urlparse(base_url.rstrip("/"))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("--base-url debe ser una URL HTTP completa.")
    websocket_scheme = "wss" if parsed.scheme == "https" else "ws"
    websocket_base = f"{websocket_scheme}://{parsed.netloc}"

    health = await asyncio.to_thread(_read_json, f"{base_url}/healthz")
    if health != {"status": "ok", "mode": "passthrough"}:
        raise RuntimeError(f"Respuesta inesperada de healthz: {health}")

    async with websockets.connect(f"{websocket_base}/ws/viewer") as viewer:
        initial = json.loads(await asyncio.wait_for(viewer.recv(), timeout=5))
        if initial.get("type") != "system_status":
            raise RuntimeError(f"Estado inicial inesperado: {initial}")

        async with websockets.connect(f"{websocket_base}/ws/camera") as camera:
            connected = await _wait_for_camera_state(viewer, True)
            if connected.get("camera_connected") is not True:
                raise RuntimeError(f"No se notificó la cámara: {connected}")

            await camera.send(JPEG_FRAME)
            received = await _wait_for_frame(viewer)
            if received != JPEG_FRAME:
                raise RuntimeError("El JPEG retransmitido no coincide byte a byte.")
            acknowledgement = json.loads(await asyncio.wait_for(camera.recv(), timeout=5))
            if acknowledgement != {"type": "frame_ack"}:
                raise RuntimeError("El servidor no confirmó la recepción del JPEG.")

            status = await asyncio.to_thread(_read_json, f"{base_url}/api/status")
            if not status.get("camera_connected") or status.get("viewer_count", 0) < 1:
                raise RuntimeError(f"Estado del relay inesperado: {status}")

        disconnected = await _wait_for_camera_state(viewer, False)
        if disconnected.get("camera_connected") is not False:
            raise RuntimeError(f"No se notificó la desconexión: {disconnected}")

    return {
        "status": "ok",
        "http": health,
        "frame_bytes": len(JPEG_FRAME),
        "relay_exact_match": True,
        "camera_disconnect_notified": True,
    }


async def _wait_for_camera_state(viewer: websockets.ClientConnection, connected: bool) -> dict[str, object]:
    for _ in range(5):
        message = await asyncio.wait_for(viewer.recv(), timeout=5)
        if isinstance(message, str):
            payload = json.loads(message)
            if payload.get("type") == "system_status" and payload.get("camera_connected") is connected:
                return payload
    raise RuntimeError(f"No se recibió el estado de cámara esperado: {connected}")


async def _wait_for_frame(viewer: websockets.ClientConnection) -> bytes:
    for _ in range(5):
        message = await asyncio.wait_for(viewer.recv(), timeout=5)
        if isinstance(message, bytes):
            return message
    raise RuntimeError("No se recibió el JPEG esperado.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    arguments = parser.parse_args()
    print(json.dumps(asyncio.run(run(arguments.base_url)), indent=2))


if __name__ == "__main__":
    main()
