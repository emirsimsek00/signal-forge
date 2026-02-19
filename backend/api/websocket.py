"""WebSocket endpoint for real-time signal and alert broadcasting."""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections with channel subscriptions.

    Clients can subscribe to channels: 'signals', 'alerts', or 'all'.
    """

    def __init__(self) -> None:
        self.connections: dict[WebSocket, set[str]] = {}
        self._heartbeat_interval = 30  # seconds

    async def connect(self, websocket: WebSocket, channels: Optional[set[str]] = None) -> None:
        await websocket.accept()
        self.connections[websocket] = channels or {"all"}

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.pop(websocket, None)

    async def broadcast(self, message: dict, channel: str = "all") -> None:
        """Broadcast a message to all connected clients subscribed to this channel."""
        dead_connections: list[WebSocket] = []

        for ws, channels in self.connections.items():
            if "all" in channels or channel in channels:
                try:
                    await ws.send_json(message)
                except Exception:
                    dead_connections.append(ws)

        # Clean up dead connections
        for ws in dead_connections:
            self.connections.pop(ws, None)

    async def broadcast_signal(self, signal_data: dict) -> None:
        """Broadcast a new signal to subscribers."""
        await self.broadcast(
            {"type": "signal", "data": signal_data},
            channel="signals",
        )

    async def broadcast_alert(self, alert_data: dict) -> None:
        """Broadcast a critical/high alert to subscribers."""
        await self.broadcast(
            {"type": "alert", "data": alert_data},
            channel="alerts",
        )

    @property
    def connection_count(self) -> int:
        return len(self.connections)


manager = ConnectionManager()


@router.websocket("/ws/signals")
async def websocket_endpoint(websocket: WebSocket):
    # Parse channel subscriptions from query params
    channels_param = websocket.query_params.get("channels", "all")
    channels = set(c.strip() for c in channels_param.split(","))

    await manager.connect(websocket, channels)
    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=manager._heartbeat_interval,
                )
                # Handle client messages
                try:
                    msg = json.loads(data)
                    msg_type = msg.get("type", "")

                    if msg_type == "subscribe":
                        new_channels = set(msg.get("channels", []))
                        manager.connections[websocket] = new_channels
                        await websocket.send_json({"type": "subscribed", "channels": list(new_channels)})
                    elif msg_type == "ping":
                        await websocket.send_json({"type": "pong"})
                    else:
                        await websocket.send_json({"type": "ack", "message": data})
                except json.JSONDecodeError:
                    await websocket.send_json({"type": "ack", "message": data})

            except asyncio.TimeoutError:
                # Send heartbeat
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)
