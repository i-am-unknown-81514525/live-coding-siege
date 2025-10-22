from datetime import datetime
from dataclasses import dataclass, field
from typing import TypedDict, SupportsIndex

from fastapi import WebSocket, WebSocketDisconnect

from .const import ws_mgr_broadcast
from .exceptions import WebsocketDisconnected


@dataclass
class WebsocketMessage:
    message: bytes
    timestamp: datetime = field(default_factory=datetime.now)


class MessageHistory(list[WebsocketMessage]):
    LIMIT: int = 100

    def add(self, message: WebsocketMessage):
        self.append(message)
        if len(self) > self.LIMIT:
            self.pop()

    def pop(self, __index: SupportsIndex = 0) -> WebsocketMessage:
        return super().pop(__index)


class Connection:
    def __init__(self, ws: WebSocket):
        self._ws = ws
        self._history: MessageHistory = MessageHistory()
        self._is_connected: bool = True

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def send(self, message: bytes) -> None:
        if not self._is_connected:
            raise WebsocketDisconnected("Websocket have been disconnected")
        await self._ws.send_bytes(message)
        return None

    async def handler(self, supress_error: bool = True) -> None:
        try:
            while True:
                message = await self._ws.receive_bytes()
                self._history.add(WebsocketMessage(message))
                await self._ws.send_bytes(
                    b"ACK"
                )  # keep-alive by responding ACK to whatever client sends
                # Client send content doesn't matter and all data should be send via HTTP(S) API instead
        except WebSocketDisconnect:
            self._is_connected = False
            if not supress_error:
                raise
            await ws_mgr_broadcast.emit("ws_disconnect", self)
        return None


class UserConnection(Connection):
    def __init__(self, meta: str, ws: WebSocket):
        self.meta = meta
        super().__init__(ws)


class VerifyResponse(TypedDict):
    resp: str
