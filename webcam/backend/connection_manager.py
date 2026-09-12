"""Estado en memoria y retransmisión sin cola de frames atrasados."""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


@dataclass(slots=True)
class ViewerConnection:
    identifier: str
    websocket: WebSocket
    frame_available: asyncio.Event = field(default_factory=asyncio.Event)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    latest_frame: bytes | None = None
    sender_task: asyncio.Task[None] | None = None
    dropped_frames: int = 0

    def offer_frame(self, frame: bytes) -> None:
        """Reemplazar el frame pendiente para privilegiar baja latencia."""
        if self.frame_available.is_set():
            self.dropped_frames += 1
        self.latest_frame = frame
        self.frame_available.set()

    async def send_json(self, payload: dict[str, Any]) -> None:
        async with self.send_lock:
            await self.websocket.send_json(payload)

    async def run_sender(self) -> None:
        while True:
            await self.frame_available.wait()
            self.frame_available.clear()
            frame = self.latest_frame
            if frame is None:
                continue
            async with self.send_lock:
                await self.websocket.send_bytes(frame)


class ConnectionManager:
    """Administra una cámara y múltiples viewers dentro de un único proceso."""

    def __init__(self) -> None:
        self._camera: WebSocket | None = None
        self._viewers: dict[str, ViewerConnection] = {}
        self._lock = asyncio.Lock()
        self._started_at = datetime.now(timezone.utc)
        self._last_frame: bytes | None = None
        self._last_frame_at: float | None = None
        self._total_frames = 0
        self._total_bytes = 0

    async def connect_camera(self, websocket: WebSocket) -> bool:
        await websocket.accept()
        async with self._lock:
            if self._camera is not None:
                await websocket.send_json(
                    {
                        "type": "error",
                        "code": "camera_already_connected",
                        "message": "Ya existe una cámara conectada.",
                    }
                )
                await websocket.close(code=1008, reason="Ya existe una cámara conectada")
                return False
            self._camera = websocket

        await self.notify_viewers()
        return True

    async def disconnect_camera(self, websocket: WebSocket) -> None:
        changed = False
        async with self._lock:
            if self._camera is websocket:
                self._camera = None
                changed = True
        if changed:
            await self.notify_viewers()

    async def connect_viewer(self, websocket: WebSocket) -> str:
        await websocket.accept()
        identifier = uuid4().hex
        viewer = ViewerConnection(identifier=identifier, websocket=websocket)
        async with self._lock:
            self._viewers[identifier] = viewer
            camera_connected = self._camera is not None
            latest_frame = self._last_frame
            viewer_count = len(self._viewers)

        viewer.sender_task = asyncio.create_task(
            viewer.run_sender(),
            name=f"viewer-sender-{identifier}",
        )
        await viewer.send_json(
            {
                "type": "system_status",
                "camera_connected": camera_connected,
                "viewer_count": viewer_count,
            }
        )
        if latest_frame is not None:
            viewer.offer_frame(latest_frame)
        return identifier

    async def disconnect_viewer(self, identifier: str) -> None:
        async with self._lock:
            viewer = self._viewers.pop(identifier, None)
        if viewer is None or viewer.sender_task is None:
            return
        viewer.sender_task.cancel()
        with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect):
            await viewer.sender_task

    async def send_to_viewer(self, identifier: str, payload: dict[str, Any]) -> None:
        async with self._lock:
            viewer = self._viewers.get(identifier)
        if viewer is not None:
            await viewer.send_json(payload)

    async def publish_frame(self, frame: bytes) -> None:
        now = time.monotonic()
        async with self._lock:
            self._last_frame = frame
            self._last_frame_at = now
            self._total_frames += 1
            self._total_bytes += len(frame)
            viewers = tuple(self._viewers.values())
        for viewer in viewers:
            viewer.offer_frame(frame)

    async def notify_viewers(self) -> None:
        async with self._lock:
            viewers = tuple(self._viewers.values())
            payload = {
                "type": "system_status",
                "camera_connected": self._camera is not None,
                "viewer_count": len(viewers),
            }
        results = await asyncio.gather(
            *(viewer.send_json(payload) for viewer in viewers),
            return_exceptions=True,
        )
        for viewer, result in zip(viewers, results, strict=True):
            if isinstance(result, Exception):
                await self.disconnect_viewer(viewer.identifier)

    async def snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        async with self._lock:
            frame_age_ms = (
                None
                if self._last_frame_at is None
                else round((now - self._last_frame_at) * 1000, 1)
            )
            return {
                "service": "camera-relay",
                "mode": "passthrough",
                "camera_connected": self._camera is not None,
                "viewer_count": len(self._viewers),
                "total_frames": self._total_frames,
                "total_bytes": self._total_bytes,
                "last_frame_age_ms": frame_age_ms,
                "started_at": self._started_at.isoformat(),
                "dropped_frames_by_viewer": {
                    identifier: viewer.dropped_frames
                    for identifier, viewer in self._viewers.items()
                },
            }
