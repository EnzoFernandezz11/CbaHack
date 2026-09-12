"""Aplicación FastAPI que retransmite JPEG desde /camera hacia /viewer."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .connection_manager import ConnectionManager
from .frame_processor import PassthroughFrameProcessor
from .settings import settings


LOGGER = logging.getLogger("camera-relay")
FRONTEND = settings.frontend_directory

if not FRONTEND.is_dir():
    raise RuntimeError(f"No existe el frontend esperado: {FRONTEND}")

manager = ConnectionManager()
processor = PassthroughFrameProcessor()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Crear el estado dentro del event loop que ejecuta la aplicación."""
    global manager
    manager = ConnectionManager()
    yield

app = FastAPI(
    title="HackCórdoba Camera Relay",
    description="Relay JPEG en tiempo real. La inferencia YOLO se integrará posteriormente.",
    version="0.1.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


def _page(name: str) -> FileResponse:
    page = Path(FRONTEND, name)
    return FileResponse(page, headers={"Cache-Control": "no-store"})


def _is_jpeg(frame: bytes) -> bool:
    return len(frame) >= 4 and frame.startswith(b"\xff\xd8") and frame.endswith(b"\xff\xd9")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return _page("index.html")


@app.get("/camera", include_in_schema=False)
async def camera_page() -> FileResponse:
    return _page("camera.html")


@app.get("/viewer", include_in_schema=False)
async def viewer_page() -> FileResponse:
    return _page("viewer.html")


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok", "mode": "passthrough"}


@app.get("/api/status")
async def relay_status() -> dict[str, object]:
    return await manager.snapshot()


@app.websocket("/ws/camera")
async def camera_socket(websocket: WebSocket) -> None:
    if not await manager.connect_camera(websocket):
        return

    LOGGER.info("Cámara conectada desde %s", websocket.client)
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break

            frame = message.get("bytes")
            if frame is None:
                if message.get("text") == "ping":
                    await websocket.send_json({"type": "pong"})
                continue
            if len(frame) > settings.maximum_frame_bytes:
                await websocket.close(code=1009, reason="Frame demasiado grande")
                break
            if not _is_jpeg(frame):
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "invalid_frame",
                        "message": "El frame recibido no es un JPEG válido.",
                    }
                )
                continue

            processed = await processor.process(frame)
            await manager.publish_frame(processed)
            # La confirmación limita la ventana del teléfono y evita que acumule
            # segundos de JPEGs cuando la red o el proceso se atrasan.
            await websocket.send_json({"type": "frame_ack"})
    except WebSocketDisconnect:
        pass
    except Exception:
        LOGGER.exception("Error procesando la conexión de la cámara")
    finally:
        await manager.disconnect_camera(websocket)
        LOGGER.info("Cámara desconectada")


@app.websocket("/ws/viewer")
async def viewer_socket(websocket: WebSocket) -> None:
    identifier = await manager.connect_viewer(websocket)
    LOGGER.info("Viewer %s conectado desde %s", identifier, websocket.client)
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("text") == "ping":
                await manager.send_to_viewer(identifier, {"type": "pong"})
    except WebSocketDisconnect:
        pass
    except Exception:
        LOGGER.exception("Error en la conexión del viewer %s", identifier)
    finally:
        await manager.disconnect_viewer(identifier)
        LOGGER.info("Viewer %s desconectado", identifier)
