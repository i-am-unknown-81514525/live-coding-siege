from collections.abc import Callable
from typing import Concatenate
from live import db
from slack.reg import Context
from utils import flatten_get_first_optional, get_all_allowed

def get_game_group[**P, T, C: Context](
    func: Callable[Concatenate[C, list[str], P], T],
) -> Callable[Concatenate[C, P], T]:
    # noinspection PyTypeChecker
    def inner(ctx: C, *args: P.args, **kwargs: P.kwargs) -> T:
        ret: list[str] = []
        if ctx.thread_ts:
            game_id = db.get_active_game_by_thread(ctx.channel_id, ctx.thread_ts)
            if game_id:
                instance = db.get_game_instance(game_id, ctx.client)
                ret = [instance.mode]
        return func(ctx, ret, *args, **kwargs)

    return inner

def require_game_thread[**P, T, C: Context](
    func: Callable[Concatenate[C, int, P], T],
) -> Callable[Concatenate[C, P], T | None]:
    def inner(ctx: C, *args: P.args, **kwargs: P.kwargs) -> T | None:
        if ctx.thread_ts is None:
            ctx.private_send(text="You can only run this in a thread")
            return None
        game_id = db.get_any_game_by_thread(ctx.channel_id, ctx.thread_ts)
        if game_id is None:
            ctx.private_send(text=f"No game instance exist in thread `{ctx.thread_ts}`")
            return None
        return func(ctx, game_id, *args, **kwargs)

    return inner


def require_game_manager[**P, T, C: Context](
    func: Callable[Concatenate[C, int, P], T],
) -> Callable[Concatenate[C, P], T | None]:
    @require_game_thread
    @get_game_group
    @flatten_get_first_optional
    def inner(ctx: C, group: str | None, game_id: int, *args: P.args, **kwargs: P.kwargs) -> T | None:
        if group:
            if "*" in get_all_allowed(group):
                return func(ctx, game_id, *args, **kwargs)
        if not db.is_game_manager(game_id, ctx.author_id):
            ctx.private_send(
                text=f'Require missing role "Game manager" in thread `{ctx.thread_ts}`'
            )
            return None
        return func(ctx, game_id, *args, **kwargs)

    return inner


def require_any_game_manager[**P, T, C: Context](
    func: Callable[Concatenate[C, int, P], T],
) -> Callable[Concatenate[C, P], T | None]:
    def inner(ctx: C,  *args: P.args, **kwargs: P.kwargs) -> T | None:
        game_id = db.get_game_mgr_active_game(ctx.author_id)
        if game_id is None:
            ctx.private_send(
                text=f'Require missing role "Game manager" in any active game.'
            )
            return None
        return func(ctx, game_id, *args, **kwargs)

    return inner