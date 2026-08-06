from __future__ import annotations

from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, project_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[project_id].add(websocket)

    def disconnect(self, project_id: str, websocket: WebSocket) -> None:
        self._connections[project_id].discard(websocket)
        if not self._connections[project_id]:
            self._connections.pop(project_id, None)

    async def broadcast(self, project_id: str, message: dict) -> None:
        stale: list[WebSocket] = []
        for websocket in tuple(self._connections.get(project_id, set())):
            try:
                await websocket.send_json(message)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.disconnect(project_id, websocket)


manager = ConnectionManager()
