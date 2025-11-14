from collections.abc import Callable
from typing import Concatenate
import os

from api import get_all_projs
import db
from reg import Context
from typing import Any


ALLOWED = os.environ["ALLOWLIST"].split(",")
AUTHORIZED_USERS = os.environ.get("AUTHORIZED_USERS", "").split(",")


def guess_week() -> int:
    projs = get_all_projs()
    max_week_num = max(projs, key=lambda p: p.week).week
    return max_week_num

def require_game_manager[**P, T, C: Context](func: Callable[Concatenate[C, int, P], T]) -> Callable[Concatenate[C, P], T | None]:
    @require_game_thread
    def inner(ctx: C, game_id: int, *args: P.args, **kwargs: P.kwargs) -> T | None:
        if not db.is_game_manager(game_id, ctx.author_id):
            ctx.private_send(text=f"Require missing role \"Game manager\" in thread `{ctx.thread_ts}`")
            return None
        return func(ctx, game_id, *args, **kwargs)
    return inner

def require_allowed[**P, T, C: Context](func: Callable[Concatenate[C, P], T]) -> Callable[Concatenate[C, P], T | None]:
    def inner(ctx: C, *args: P.args, **kwargs: P.kwargs) -> T | None:
        if ctx.author_id not in ALLOWED and ctx.author_id not in AUTHORIZED_USERS:
            return None
        return func(ctx, *args, **kwargs)
    return inner

def require_authorised[**P, T, C: Context](func: Callable[Concatenate[C, P], T]) -> Callable[Concatenate[C, P], T | None]:
    def inner(ctx: C, *args: P.args, **kwargs: P.kwargs) -> T | None:
        if ctx.author_id not in AUTHORIZED_USERS:
            return None
        return func(ctx, *args, **kwargs)
    return inner

def require_game_thread[**P, T, C: Context](func: Callable[Concatenate[C, int, P], T]) -> Callable[Concatenate[C, P], T | None]:
    def inner(ctx: C, *args: P.args, **kwargs: P.kwargs) -> T | None:
        if ctx.thread_ts is None:
            ctx.private_send(text="You can only run this in a thread")
            return None
        game_id = db.get_active_game_by_thread(ctx.channel_id, ctx.thread_ts)
        if game_id is None:
            ctx.private_send(text=f"No game instance exist in thread `{ctx.thread_ts}`")
            return None
        return func(ctx, game_id, *args, **kwargs)
    return inner