from collections.abc import Callable

import typing
import asyncio
from fastapi import FastAPI, WebSocket
import threading
import sys
from types import TracebackType
from dataclasses import dataclass


type ExcInfo[E: BaseException] = tuple[type[E], E, TracebackType]

@dataclass
class ThreadEx[R, E: BaseException]:
    completed: bool = False
    result: R | None = None
    error: ExcInfo[E] | None = None


async def get_result[**P, R, E: BaseException](fn: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
    obj: ThreadEx[R, E] = ThreadEx[R, E]()
    def wrapper():
        try:
            result = fn(*args, **kwargs)
        except:
            exc_info = sys.exc_info()
            obj.error = exc_info  # pyright: ignore[reportAttributeAccessIssue]
        else:
            obj.result = result
        finally:
            obj.completed = True
    thread = threading.Thread(target=wrapper)
    thread.start()
    async def checker() -> R:
        while not obj.completed:
            await asyncio.sleep(0.1)
        if obj.error is not None:
            raise obj.error[1].with_traceback(obj.error[2])
        r: R | None = obj.result
        return r # pyright: ignore[reportReturnType]
    return await checker()

app = FastAPI()

client_secret_hook: list[WebSocket] = []

@app.websocket("/client-secret-ws")
async def client_ws(websocket: WebSocket):
    await websocket.accept()
    ...