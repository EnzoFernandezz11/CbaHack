"""Pruebas HTTP y WebSocket contra un proceso Uvicorn real."""

from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
import websockets


WEB_ROOT = Path(__file__).resolve().parents[1]
JPEG_FRAME = b"\xff\xd8test-frame\xff\xd9"


def _unused_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _get(url: str) -> tuple[int, str, bytes]:
    with urllib.request.urlopen(url, timeout=3) as response:  # noqa: S310 - URL local
        return response.status, response.headers.get_content_type(), response.read()


@pytest.fixture(scope="module")
def server_url() -> Iterator[str]:
    port = _unused_port()
    base_url = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.main:app",
            "--app-dir",
            str(WEB_ROOT),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=WEB_ROOT.parent,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 12
    try:
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"Uvicorn finalizó anticipadamente con código {process.returncode}.")
            try:
                status, _, _ = _get(f"{base_url}/healthz")
                if status == 200:
                    break
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
        else:
            raise TimeoutError("Uvicorn no respondió dentro de 12 segundos.")

        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_pages_and_healthcheck(server_url: str) -> None:
    for route, expected_type, expected_text in (
        ("/", "text/html", "Conexión de cámara"),
        ("/camera", "text/html", "Transmitir cámara"),
        ("/viewer", "text/html", "Visor en tiempo real"),
        ("/static/styles.css", "text/css", ":root"),
        ("/static/camera.js", "text/javascript", '"use strict"'),
        ("/static/viewer.js", "text/javascript", '"use strict"'),
    ):
        status, content_type, body = _get(f"{server_url}{route}")
        assert status == 200
        assert content_type == expected_type
        assert expected_text in body.decode("utf-8")

    status, content_type, body = _get(f"{server_url}/healthz")
    assert status == 200
    assert content_type == "application/json"
    assert json.loads(body) == {"status": "ok", "mode": "passthrough"}


async def _relay_frame(server_url: str) -> None:
    websocket_base = server_url.replace("http://", "ws://", 1)
    async with websockets.connect(f"{websocket_base}/ws/viewer") as viewer:
        initial = json.loads(await asyncio.wait_for(viewer.recv(), timeout=3))
        assert initial["type"] == "system_status"
        assert initial["camera_connected"] is False

        async with websockets.connect(f"{websocket_base}/ws/camera") as camera:
            connected = json.loads(await asyncio.wait_for(viewer.recv(), timeout=3))
            assert connected["camera_connected"] is True

            await camera.send(JPEG_FRAME)
            assert await asyncio.wait_for(viewer.recv(), timeout=3) == JPEG_FRAME

            _, _, status_body = await asyncio.to_thread(_get, f"{server_url}/api/status")
            status = json.loads(status_body)
            assert status["camera_connected"] is True
            assert status["viewer_count"] == 1
            assert status["total_frames"] >= 1

        disconnected = json.loads(await asyncio.wait_for(viewer.recv(), timeout=3))
        assert disconnected["camera_connected"] is False


def test_binary_frame_is_relayed_from_camera_to_viewer(server_url: str) -> None:
    asyncio.run(_relay_frame(server_url))


async def _send_invalid_frame(server_url: str) -> None:
    websocket_base = server_url.replace("http://", "ws://", 1)
    async with websockets.connect(f"{websocket_base}/ws/camera") as camera:
        await camera.send(b"not-a-jpeg")
        response = json.loads(await asyncio.wait_for(camera.recv(), timeout=3))
        assert response["type"] == "error"
        assert response["code"] == "invalid_frame"


def test_invalid_frame_returns_a_clear_error(server_url: str) -> None:
    asyncio.run(_send_invalid_frame(server_url))
