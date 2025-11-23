from collections.abc import Callable

from contextlib import asynccontextmanager
import json
import logging
import os
import typing
import asyncio
from fastapi import FastAPI, WebSocket, Request, Depends, HTTPException
import threading
import sys
from types import TracebackType
from dataclasses import dataclass
from fastapi.staticfiles import StaticFiles
import jwt

from live.base import get_module
from ws_mgr import controller, schema, signals
import uvicorn
import live.db as db
from slack_sdk.socket_mode import SocketModeClient


type ExcInfo[E: BaseException] = tuple[type[E], E, TracebackType]


@dataclass
class ThreadEx[R, E: BaseException]:
    completed: bool = False
    result: R | None = None
    error: ExcInfo[E] | None = None


async def get_result[**P, R, E: BaseException](
    fn: Callable[P, R], *args: P.args, **kwargs: P.kwargs
) -> R:
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
        return r  # pyright: ignore[reportReturnType]

    return await checker()


@asynccontextmanager
async def lifespan(_: FastAPI):
    loop = asyncio.get_running_loop()
    signals.ROOT.set_loop(loop)
    signals.LOOP = loop
    yield


app = FastAPI(lifespan=lifespan)


async def check_jwt(req: Request) -> str:
    try:
        result = jwt.decode(
            req.cookies["JWT"],
            os.environ["JWT_SECRET"],
            algorithms=["HS256"],
            issuer="bot",
            audience="web",
        )
        return result["user_id"]
    except:
        logging.info("Error on jwt check", exc_info=True)
        raise HTTPException(401, "Unauthorized")


async def check_jwt_ws(websocket: WebSocket) -> str | None:
    try:
        token = websocket.cookies["JWT"]
        result = jwt.decode(
            token,
            os.environ["JWT_SECRET"],
            algorithms=["HS256"],
            issuer="bot",
            audience="web",
        )
        return result["user_id"]
    except:
        logging.info("Error on jwt check", exc_info=True)
        return None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/validate")
async def validate(user_id: typing.Annotated[str, Depends(check_jwt)]):
    return {"user_id": user_id}


@app.get("/client-secret")
async def client_secret_curr(user_id: typing.Annotated[str, Depends(check_jwt)]):
    game_id = await get_result(db.get_game_mgr_active_game, user_id)
    if game_id is None:
        raise HTTPException(404, "Cannot find a game that you are actively managing.")

    secrets = await get_result(db.get_latest_secrets, game_id)
    if not secrets:
        raise HTTPException(419, "No secrets found")
    client_secret, _ = secrets
    return {"client_secret": client_secret}


@app.get("/accept")
async def accept_turn(
    user_id: typing.Annotated[str, Depends(check_jwt)], request: Request
):
    app = request.app
    client: SocketModeClient = app.state.slack_client
    game_id = await get_result(db.get_game_mgr_active_game, user_id)
    if game_id is None:
        raise HTTPException(404, "Cannot find a game that you are actively managing")

    turn_detail = await get_result(db.get_active_turn_details, game_id)

    if not turn_detail:
        raise HTTPException(419, "Unable to find an active turn")

    turn_user_id: str = turn_detail[0]

    await get_result(db.update_turn_status, game_id, turn_user_id, "COMPLETED")
    await controller.connection_manager.send(
        f"turn/{game_id}",
        json.dumps(
            {
                "type": "turn_update",
                "status": "COMPLETED",
                "user_id": user_id,
                "user_name": (await get_result(db.get_user_names, [user_id])).get(
                    user_id, user_id
                ),
            }
        ).encode(),
    )

    instance = await get_result(db.get_game_instance, game_id, client.web_client)
    try:
        await get_result(
            client.web_client.chat_postMessage,
            channel=instance.channel_id,
            text=f"Your turn have been marked as *COMPLETED* by the game manager <@{user_id}> via web dashboard)",
            thread_ts=instance.thread_ts,
        )
    except Exception:
        logging.warning("Error sending message to slack", exc_info=True)

    return "ok"


@app.get("/reject")
async def reject_turn(
    user_id: typing.Annotated[str, Depends(check_jwt)], request: Request
):
    app = request.app
    client: SocketModeClient = app.state.slack_client
    game_id = await get_result(db.get_game_mgr_active_game, user_id)
    if game_id is None:
        raise HTTPException(404, "Cannot find a game that you are actively manging")
    turn_detail = await get_result(db.get_active_turn_details, game_id)

    if not turn_detail:
        raise HTTPException(419, "Unable to fine an active turn")

    turn_user_id: str = turn_detail[0]

    await get_result(db.update_turn_status, game_id, turn_user_id, "FAILED")

    await controller.connection_manager.send(
        f"turn/{game_id}",
        json.dumps(
            {
                "type": "turn_update",
                "status": "FAILED",
                "user_id": user_id,
                "user_name": (await get_result(db.get_user_names, [user_id])).get(
                    user_id, user_id
                ),
            }
        ).encode(),
    )
    instance = await get_result(db.get_game_instance, game_id, client.web_client)
    try:
        await get_result(
            client.web_client.chat_postMessage,
            channel=instance.channel_id,
            text=f"Your turn have been marked as *FAILED* by the game manager <@{user_id}> via web dashboard)",
            thread_ts=instance.thread_ts,
        )
    except Exception:
        logging.warning("Error sending message to slack", exc_info=True)
    return "ok"


@app.get("/turn-status")
async def get_turn_status(user_id: typing.Annotated[str, Depends(check_jwt)]):
    game_id = await get_result(db.get_game_mgr_active_game, user_id)
    if game_id is None:
        raise HTTPException(404, "Cannot find a game that you are actively managing.")

    active_turn = await get_result(db.get_active_turn_details, game_id)
    if not active_turn:
        return {"status": "NO_ACTIVE_TURN"}

    turn_user_id = active_turn["user_id"]
    user_names_map = await get_result(db.get_user_names, [turn_user_id])
    user_name = user_names_map.get(turn_user_id, turn_user_id)

    response = {
        "status": active_turn["status"],
        "user_id": turn_user_id,
        "user_name": user_name,
    }

    if (
        active_turn["status"] in ("IN_PROGRESS", "ACCEPTED")
        and active_turn["start_time"]
    ):
        start_time = db.datetime.fromisoformat(active_turn["start_time"])
        duration = active_turn["assigned_duration_seconds"]
        response["endTime"] = start_time.timestamp() + duration

    return response


@app.get("/tickets")
async def get_tickets(
    user_id: typing.Annotated[str, Depends(check_jwt)], request: Request
) -> dict[str, tuple[str, int, str]]:
    game_id = await get_result(db.get_game_mgr_active_game, user_id)
    if game_id is None:
        raise HTTPException(404, "Cannot find a game that you are actively managing.")

    users = await get_result(db.get_huddle_participants, game_id)
    client = request.app.state.slack_client

    result: dict[str, tuple[str, int, str]] = {}
    instance = await get_result(db.get_game_instance, game_id, client.web_client)
    module = await get_result(get_module, instance)
    user_tickets = await get_result(module.get_tickets, users)
    for user, ticket in user_tickets.items():
        await get_result(db.add_game_participant, game_id, user, ticket)
    for user in users:
        user_info = await get_result(db.get_slack_user, user)
        if not user_info:
            continue
        result[user] = (
            user_info[0],
            user_tickets.get(user, 0),
            (user_info[1] or "empty.png"),
        )
    return result


@app.get("/tickets-no-update")
async def get_tickets_no_update(
    user_id: typing.Annotated[str, Depends(check_jwt)],
) -> dict[str, tuple[str, int, str]]:
    game_id = await get_result(db.get_game_mgr_active_game, user_id)
    if game_id is None:
        raise HTTPException(404, "Cannot find a game that you are actively managing.")

    users = await get_result(db.get_huddle_participants, game_id)

    result: dict[str, tuple[str, int, str]] = {}
    user_tickets = await get_result(db.get_all_participant_ticket_counts, game_id)
    for user in users:
        user_info = await get_result(db.get_slack_user, user)
        if not user_info:
            continue
        result[user] = (
            user_info[0],
            user_tickets.get(user, 0),
            (user_info[1] or "empty.png"),
        )
    return result


@app.websocket("/client-secret-ws")
async def client_ws(
    websocket: WebSocket, user_id: typing.Annotated[str | None, Depends(check_jwt_ws)]
):
    await websocket.accept()
    if user_id is None:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    game_id = await get_result(db.get_game_mgr_active_game, user_id)
    if game_id is None:
        await websocket.close(
            code=4004, reason="Cannot find a game that you are actively managing."
        )
        return
    conn = schema.UserConnection(meta=f"client/{game_id}", ws=websocket)
    controller.connection_manager.add(conn)
    await conn.handler()


@app.websocket("/turn-ws")
async def turn_ws(
    websocket: WebSocket, user_id: typing.Annotated[str | None, Depends(check_jwt_ws)]
):
    await websocket.accept()
    if user_id is None:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    game_id = await get_result(db.get_game_mgr_active_game, user_id)
    if game_id is None:
        await websocket.close(
            code=4004, reason="Cannot find a game that you are actively managing."
        )
        return
    conn = schema.UserConnection(meta=f"turn/{game_id}", ws=websocket)
    controller.connection_manager.add(conn)
    await conn.handler()


@app.websocket("/ticket-ws")
async def ticket_ws(
    websocket: WebSocket, user_id: typing.Annotated[str | None, Depends(check_jwt_ws)]
):
    # Note this won't actually provide the entire list, Please use /ticket-no-update endpoint - current me
    await websocket.accept()
    if user_id is None:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    game_id = await get_result(db.get_game_mgr_active_game, user_id)
    if game_id is None:
        await websocket.close(
            code=4004, reason="Cannot find a game that you are actively managing."
        )
        return
    conn = schema.UserConnection(meta=f"ticket/{game_id}", ws=websocket)
    controller.connection_manager.add(conn)
    await conn.handler()


app.mount("/", StaticFiles(directory="static", html=True), name="static")


def start_server(client: SocketModeClient):
    app.state.slack_client = client
    uvicorn.run(app, host="0.0.0.0", port=8000)


def start(client: SocketModeClient):
    thread = threading.Thread(target=start_server, args=(client,))
    thread.start()
