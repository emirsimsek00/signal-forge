"""WebSocket endpoint for real-time signal updates."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections for broadcasting."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        for conn in self.active_connections:
            try:
                await conn.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


@router.websocket("/ws/signals")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for now; will be used for chat queries in Phase 2
            await websocket.send_json({"type": "ack", "message": data})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
