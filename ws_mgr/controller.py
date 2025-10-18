from collections import defaultdict
from typing import TYPE_CHECKING

from .schema import UserConnection
from .const import ws_mgr_broadcast


class ConnectionManagerCls:
    def __init__(self):
        self._connection_pool: dict[str, list[UserConnection]] = defaultdict(list)

    def add(self, conn: UserConnection):
        self._connection_pool[conn.meta].append(conn)

    async def send(self, meta: str, message: bytes):
        for conn in self._connection_pool[meta]:
            if conn.is_connected:
                await conn.send(message)

    def remove(self, conn: UserConnection):
        if conn in self._connection_pool[conn.meta]:
            self._connection_pool[conn.meta].remove(conn)

async def disconnect_handler(conn: UserConnection) -> None:
    if not isinstance(conn, UserConnection):
        raise ValueError(f"UserConnection expected, {type(conn)} given")
    connection_manager.remove(conn)

ws_mgr_broadcast.subscribe(disconnect_handler, "ws_disconnect")

connection_manager: ConnectionManagerCls = ConnectionManagerCls()