"""
WebSocket Connection Manager for Vigil Real-Time Push

Manages WebSocket connections, heartbeat/ping-pong, and forwards events
from the event bus to connected clients.
"""

import os
import json
import asyncio
import logging
from typing import Dict, Set, Optional
from fastapi import WebSocket

logger = logging.getLogger(__name__)

MAX_CONNECTIONS = int(os.environ.get("WS_MAX_CONNECTIONS", 10))
HEARTBEAT_INTERVAL = int(os.environ.get("WS_HEARTBEAT_INTERVAL", 30))  # seconds


class WebSocketManager:
    """Manages WebSocket connections and forwards events from the event bus."""

    def __init__(self, max_connections: int = MAX_CONNECTIONS):
        self._connections: Dict[str, WebSocket] = {}
        self._max_connections = max_connections
        self._heartbeat_tasks: Dict[str, asyncio.Task] = {}

    @property
    def active_count(self) -> int:
        return len(self._connections)

    @property
    def has_capacity(self) -> bool:
        return self.active_count < self._max_connections

    async def connect(self, connection_id: str, websocket: WebSocket) -> bool:
        """
        Accept and track a new WebSocket connection.
        Returns True if connection was accepted, False if at capacity.
        """
        if not self.has_capacity:
            logger.warning(
                f"WebSocket connection rejected: max capacity ({self._max_connections}) reached"
            )
            return False

        await websocket.accept()
        self._connections[connection_id] = websocket
        self._heartbeat_tasks[connection_id] = asyncio.create_task(
            self._heartbeat_loop(connection_id, websocket)
        )
        logger.info(f"WebSocket connected: {connection_id} (total: {self.active_count})")

        # Send welcome message
        await self._send_json(
            websocket,
            {
                "type": "welcome",
                "connection_id": connection_id,
                "message": "Connected to Vigil WebSocket",
                "active_connections": self.active_count,
            },
        )
        return True

    async def disconnect(self, connection_id: str) -> None:
        """Remove a WebSocket connection and clean up resources."""
        if connection_id in self._connections:
            del self._connections[connection_id]
            logger.info(
                f"WebSocket disconnected: {connection_id} (total: {self.active_count})"
            )

        if connection_id in self._heartbeat_tasks:
            task = self._heartbeat_tasks[connection_id]
            if not task.done():
                task.cancel()
            del self._heartbeat_tasks[connection_id]

    async def send_to(self, connection_id: str, data: dict) -> bool:
        """Send a JSON message to a specific connection."""
        ws = self._connections.get(connection_id)
        if ws is None:
            return False
        return await self._send_json(ws, data)

    async def broadcast(self, data: dict) -> None:
        """Broadcast a JSON message to all connected clients."""
        disconnected = []
        for conn_id, ws in list(self._connections.items()):
            success = await self._send_json(ws, data)
            if not success:
                disconnected.append(conn_id)

        # Clean up any stale connections discovered during broadcast
        for conn_id in disconnected:
            await self.disconnect(conn_id)

    async def _send_json(self, websocket: WebSocket, data: dict) -> bool:
        """Send JSON to a WebSocket, handling errors gracefully."""
        try:
            await websocket.send_json(data)
            return True
        except Exception as e:
            logger.warning(f"WebSocket send failed: {e}")
            return False

    async def _heartbeat_loop(self, connection_id: str, websocket: WebSocket) -> None:
        """
        Periodically send ping messages to detect stale connections.
        If a ping fails, the connection is considered dead and will be cleaned up.
        """
        try:
            while connection_id in self._connections:
                await asyncio.sleep(HEARTBEAT_INTERVAL)
                if connection_id in self._connections:
                    success = await self._send_json(
                        websocket, {"type": "ping", "timestamp": asyncio.get_event_loop().time()}
                    )
                    if not success:
                        logger.warning(f"Heartbeat failed for {connection_id}, disconnecting")
                        await self.disconnect(connection_id)
                        break
        except asyncio.CancelledError:
            pass  # Expected during shutdown/disconnect
        except Exception as e:
            logger.error(f"Heartbeat loop error for {connection_id}: {e}")
            await self.disconnect(connection_id)


# Singleton instance
ws_manager = WebSocketManager()
