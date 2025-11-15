from collections.abc import Callable
from typing import Concatenate
import os
import re

from api import get_all_projs
import db
from reg import Context
from typing import overload, Literal
from config import AllGroupConfig, get_config


ALLOWED = os.environ["ALLOWLIST"].split(",")
AUTHORIZED_USERS = os.environ.get("AUTHORIZED_USERS", "").split(",")

def check_namespace_match(current: list[str], require: list[str]) -> bool:
    for req in require:
        if req.startswith("r:"):
            regex = req.removeprefix("r:")
            for key in current:
                if re.fullmatch(regex, key):
                    return True
        else:
            if req in current:
                return True
    return False

def get_match_group(current:list[str], configs: AllGroupConfig) -> list[str]:
    ret: list[str] = []
    for group_name, group_config in configs.items():
        if check_namespace_match(current, group_config["namespace"]):
            ret.append(group_name)
    return ret

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

def require_allowed[**P, T, C: Context](func: Callable[Concatenate[C, list[str], P], T]) -> Callable[Concatenate[C, P], T | None]:
    @get_group
    def inner(ctx: C, groups: list[str], *args: P.args, **kwargs: P.kwargs) -> T | None:
        configs = get_config()["bot"]["group"]
        clo = groups.copy()
        for group in groups:
            if ctx.author_id not in  configs[group]["allowed"] and ctx.author_id not in configs[group]["authorized"]:
                clo.remove(group)
        if not clo:
            group_names = ", ".join(f"\"{name}\"" for name in groups)
            ctx.private_send(text=f"Missing required group of \"Allowed\" or \"Authorised\" in one of {group_names}")
            return None
        return func(ctx, clo, *args, **kwargs)
    return inner

def require_authorised[**P, T, C: Context](func: Callable[Concatenate[C, list[str], P], T]) -> Callable[Concatenate[C, P], T | None]:
    @get_group
    def inner(ctx: C, groups: list[str], *args: P.args, **kwargs: P.kwargs) -> T | None:
        configs = get_config()["bot"]["group"]
        clo = groups.copy()
        for group in groups:
            if ctx.author_id not in configs[group]["authorized"]:
                clo.remove(group)
        if not clo:
            group_names = ", ".join(f"\"{name}\"" for name in groups)
            ctx.private_send(text=f"Missing required group of \"Authorised\" in one of {group_names}")
            return None
        return func(ctx, clo, *args, **kwargs)
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

def get_group[**P, T, C: Context](func: Callable[Concatenate[C, list[str], P], T]) -> Callable[Concatenate[C, P]]:
    def inner(ctx: C, *args: P.args, **kwargs: P.kwargs) -> T:
        configs = get_config()["bot"]["group"]
        return func(ctx, get_match_group(ctx.list_namespace, configs), *args, **kwargs)
    return inner

@overload
def require_group[**P, T, C: Context](group: str, forwarding: Literal[False] = False) -> Callable[[Callable[Concatenate[C, P], T]], Callable[Concatenate[C, list[str], P], T | None]]: ... # pyright: ignore[reportOverlappingOverload]

@overload
def require_group[**P, T, C: Context](group: str, forwarding: Literal[True] = False) -> Callable[[Callable[Concatenate[C, list[str], P], T]], Callable[Concatenate[C, list[str], P], T | None]]: ... # pyright: ignore[reportArgumentType]


def require_group[**P, T, C: Context](group: str, forwarding: bool = False) -> Callable[[Callable[Concatenate[C, list[str], P], T]], Callable[Concatenate[C, list[str], P], T | None]] | Callable[[Callable[Concatenate[C, P], T]], Callable[Concatenate[C, list[str], P], T | None]]:
    def outer_fwd(func: Callable[Concatenate[C, list[str], P], T]) -> Callable[Concatenate[C, list[str], P], T | None]:
        def inner(ctx: C, groups: list[str], *args: P.args, **kwargs: P.kwargs) -> T | None:
            if group not in groups:
                ctx.private_send(text=f"Missing required group {group}")
                return None
            return func(ctx, [group], *args, **kwargs)
        return inner
    
    def outer_no_fwd(func: Callable[Concatenate[C, P], T]) -> Callable[Concatenate[C, list[str], P], T | None]:
        def inner(ctx: C, groups: list[str], *args: P.args, **kwargs: P.kwargs) -> T | None:
            if group not in groups:
                ctx.private_send(text=f"Missing required group {group}")
                return None
            return func(ctx, *args, **kwargs)
        return inner
    if forwarding:
        return outer_fwd
    return outer_no_fwd

@overload
def require_groups[**P, T, C: Context](groups: list[str], forwarding: Literal[False] = False) -> Callable[[Callable[Concatenate[C, P], T]], Callable[Concatenate[C, list[str], P], T | None]]: ... # pyright: ignore[reportOverlappingOverload]

@overload
def require_groups[**P, T, C: Context](groups: list[str], forwarding: Literal[True] = False) -> Callable[[Callable[Concatenate[C, list[str], P], T]], Callable[Concatenate[C, list[str], P], T | None]]: ... # pyright: ignore[reportArgumentType]


def require_groups[**P, T, C: Context](groups: list[str], forwarding: bool = False) -> Callable[[Callable[Concatenate[C, list[str], P], T]], Callable[Concatenate[C, list[str], P], T | None]] | Callable[[Callable[Concatenate[C, P], T]], Callable[Concatenate[C, list[str], P], T | None]]:
    def outer_fwd(func: Callable[Concatenate[C, list[str], P], T]) -> Callable[Concatenate[C, list[str], P], T | None]:
        def inner(ctx: C, inner_group: list[str], *args: P.args, **kwargs: P.kwargs) -> T | None:
            overlap = set(groups).intersection(inner_group)
            if not overlap:
                group_names = ", ".join(f"\"{name}\"" for name in groups)
                ctx.private_send(text=f"Missing required group of {group_names}")
                return None
            return func(ctx, list(overlap), *args, **kwargs)
        return inner
    
    def outer_no_fwd(func: Callable[Concatenate[C, P], T]) -> Callable[Concatenate[C, list[str], P], T | None]:
        def inner(ctx: C, inner_group: list[str], *args: P.args, **kwargs: P.kwargs) -> T | None:
            overlap = set(groups).intersection(inner_group)
            if not overlap:
                group_names = ", ".join(f"\"{name}\"" for name in groups)
                ctx.private_send(text=f"Missing required group of {group_names}")
                return None
            return func(ctx, *args, **kwargs)
        return inner
    if forwarding:
        return outer_fwd
    
    # def outer(func: Callable[Concatenate[C, list[str], P], T]) -> Callable[Concatenate[C, P], T | None] | Callable[Concatenate[C, list[str], P], T | None]:
    #     def inner(ctx: C, inner: list[str], *args: P.args, **kwargs: P.kwargs) -> T | None:
    #         overlap = set(groups).intersection(inner)
    #         if not overlap:
    #             group_names = ", ".join(f"\"{name}\"" for name in groups)
    #             ctx.private_send(text=f"Missing required group of {group_names}")
    #             return None
    #         if forwarding:
    #             return func(ctx, list(overlap), *args, **kwargs)
    #         return func(ctx, *args, **kwargs) # pyright: ignore[reportCallIssue]
    #     return inner
    if forwarding:
        return outer_fwd
    return outer_no_fwd
