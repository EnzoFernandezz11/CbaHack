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
        if initial.get("camera_connected") is not False:
            raise RuntimeError(f"Estado inicial inesperado: {initial}")

        async with websockets.connect(f"{websocket_base}/ws/camera") as camera:
            connected = json.loads(await asyncio.wait_for(viewer.recv(), timeout=5))
            if connected.get("camera_connected") is not True:
                raise RuntimeError(f"No se notificó la cámara: {connected}")

            await camera.send(JPEG_FRAME)
            received = await asyncio.wait_for(viewer.recv(), timeout=5)
            if received != JPEG_FRAME:
                raise RuntimeError("El JPEG retransmitido no coincide byte a byte.")

            status = await asyncio.to_thread(_read_json, f"{base_url}/api/status")
            if not status.get("camera_connected") or status.get("viewer_count") != 1:
                raise RuntimeError(f"Estado del relay inesperado: {status}")

        disconnected = json.loads(await asyncio.wait_for(viewer.recv(), timeout=5))
        if disconnected.get("camera_connected") is not False:
            raise RuntimeError(f"No se notificó la desconexión: {disconnected}")

    return {
        "status": "ok",
        "http": health,
        "frame_bytes": len(JPEG_FRAME),
        "relay_exact_match": True,
        "camera_disconnect_notified": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    arguments = parser.parse_args()
    print(json.dumps(asyncio.run(run(arguments.base_url)), indent=2))


if __name__ == "__main__":
    main()

