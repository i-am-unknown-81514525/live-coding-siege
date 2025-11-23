from collections.abc import Callable
from typing import Concatenate
import os
import re

from siege.api import get_all_projs
import live.db as db
from reg import Context
from typing import overload, Literal
from config import AllGroupConfig, get_config


# ALLOWED = os.environ["ALLOWLIST"].split(",")
# AUTHORIZED_USERS = os.environ.get("AUTHORIZED_USERS", "").split(",")

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

def get_is_authorized(user_id: str, group: str) -> bool:
    configs = get_config()["bot"]["group"]
    if group not in configs:
        return False
    return user_id in configs[group]["authorized"]

def get_is_allowed(user_id: str, group: str) -> bool:
    configs = get_config()["bot"]["group"]
    if group not in configs:
        return False
    return user_id in configs[group]["allowed"] or user_id in configs[group]["authorized"]

def require_allowed[**P, T, C: Context](func: Callable[Concatenate[C, list[str], P], T]) -> Callable[Concatenate[C, list[str], P], T | None]:
    @filter_allowed
    def inner(ctx: C, groups: list[str], *args: P.args, **kwargs: P.kwargs) -> T | None:
        if not groups:
            group_names = ", ".join(f"\"{name}\"" for name in groups)
            ctx.private_send(text=f"Missing required group of \"Allowed\" or \"Authorised\" in one of {group_names}")
            return None
        return func(ctx, groups, *args, **kwargs)
    return inner

def require_authorised[**P, T, C: Context](func: Callable[Concatenate[C, list[str], P], T]) -> Callable[Concatenate[C, list[str], P], T | None]:
    @filter_authorised
    def inner(ctx: C, groups: list[str], *args: P.args, **kwargs: P.kwargs) -> T | None:
        if not groups:
            group_names = ", ".join(f"\"{name}\"" for name in groups)
            ctx.private_send(text=f"Missing required group of \"Authorised\" in one of {group_names}")
            return None
        return func(ctx, groups, *args, **kwargs)
    return inner

def filter_allowed[**P, T, C: Context](func: Callable[Concatenate[C, list[str], P], T]) -> Callable[Concatenate[C, list[str], P], T]:
    def inner(ctx: C, groups: list[str], *args: P.args, **kwargs: P.kwargs) -> T:
        configs = get_config()["bot"]["group"]
        clo = groups.copy()
        for group in groups:
            if ctx.author_id not in  configs[group]["allowed"] and ctx.author_id not in configs[group]["authorized"]:
                clo.remove(group)
        return func(ctx, clo, *args, **kwargs)
    return inner

def filter_authorised[**P, T, C: Context](func: Callable[Concatenate[C, list[str], P], T]) -> Callable[Concatenate[C, list[str], P], T]:
    def inner(ctx: C, groups: list[str], *args: P.args, **kwargs: P.kwargs) -> T:
        configs = get_config()["bot"]["group"]
        clo = groups.copy()
        for group in groups:
            if ctx.author_id not in configs[group]["authorized"]:
                clo.remove(group)
        return func(ctx, clo, *args, **kwargs)
    return inner


def get_group[**P, T, C: Context](func: Callable[Concatenate[C, list[str], P], T]) -> Callable[Concatenate[C, P], T]:
    def inner(ctx: C, *args: P.args, **kwargs: P.kwargs) -> T:
        configs = get_config()["bot"]["group"]
        return func(ctx, get_match_group(ctx.list_namespace, configs), *args, **kwargs)
    return inner

def filter_groups[**P, T, C: Context](groups: list[str]) -> Callable[[Callable[Concatenate[C, list[str], P], T]], Callable[Concatenate[C, list[str], P], T]]:
    def outer(func: Callable[Concatenate[C, list[str], P], T]) -> Callable[Concatenate[C, list[str], P], T]:
        def inner(ctx: C, curr_group: list[str], *args: P.args, **kwargs: P.kwargs) -> T:
            return func(ctx, list(set(groups).intersection(curr_group)), *args, **kwargs)
        return inner
    return outer

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
    if forwarding:
        return outer_fwd
    return outer_no_fwd


@overload
def has_group[**P, T, C: Context](group: str, forwarding: Literal[False] = False) -> Callable[[Callable[Concatenate[C, bool, P], T]], Callable[Concatenate[C, list[str], P], T | None]]: ... # pyright: ignore[reportOverlappingOverload]

@overload
def has_group[**P, T, C: Context](group: str, forwarding: Literal[True] = False) -> Callable[[Callable[Concatenate[C, bool, list[str], P], T]], Callable[Concatenate[C, list[str], P], T | None]]: ... # pyright: ignore[reportArgumentType]


def has_group[**P, T, C: Context](group: str, forwarding: bool = False) -> Callable[[Callable[Concatenate[C, bool, list[str], P], T]], Callable[Concatenate[C, list[str], P], T | None]] | Callable[[Callable[Concatenate[C, bool, P], T]], Callable[Concatenate[C, list[str], P], T | None]]:
    def outer_fwd(func: Callable[Concatenate[C, bool, list[str], P], T]) -> Callable[Concatenate[C, list[str], P], T | None]:
        def inner(ctx: C, groups: list[str], *args: P.args, **kwargs: P.kwargs) -> T | None:
            ret = [group]
            if group not in groups:
                ret.remove(group)
            return func(ctx, bool(ret), ret, *args, **kwargs)
        return inner
    
    def outer_no_fwd(func: Callable[Concatenate[C, bool, P], T]) -> Callable[Concatenate[C, list[str], P], T | None]:
        def inner(ctx: C, groups: list[str], *args: P.args, **kwargs: P.kwargs) -> T | None:
            return func(ctx, group in groups, *args, **kwargs)
        return inner
    if forwarding:
        return outer_fwd
    return outer_no_fwd

@overload
def have_one_of_groups[**P, T, C: Context](groups: list[str], forwarding: Literal[False] = False) -> Callable[[Callable[Concatenate[C, bool, P], T]], Callable[Concatenate[C, list[str], P], T | None]]: ... # pyright: ignore[reportOverlappingOverload]

@overload
def have_one_of_groups[**P, T, C: Context](groups: list[str], forwarding: Literal[True] = False) -> Callable[[Callable[Concatenate[C, bool, list[str], P], T]], Callable[Concatenate[C, list[str], P], T | None]]: ... # pyright: ignore[reportArgumentType]


def have_one_of_groups[**P, T, C: Context](groups: list[str], forwarding: bool = False) -> Callable[[Callable[Concatenate[C, bool, list[str], P], T]], Callable[Concatenate[C, list[str], P], T | None]] | Callable[[Callable[Concatenate[C, bool, P], T]], Callable[Concatenate[C, list[str], P], T | None]]:
    def outer_fwd(func: Callable[Concatenate[C, bool, list[str], P], T]) -> Callable[Concatenate[C, list[str], P], T | None]:
        def inner(ctx: C, inner_group: list[str], *args: P.args, **kwargs: P.kwargs) -> T | None:
            overlap = set(groups).intersection(inner_group)
            return func(ctx, bool(overlap),list(overlap), *args, **kwargs)
        return inner
    
    def outer_no_fwd(func: Callable[Concatenate[C, bool, P], T]) -> Callable[Concatenate[C, list[str], P], T | None]:
        def inner(ctx: C, inner_group: list[str], *args: P.args, **kwargs: P.kwargs) -> T | None:
            overlap = set(groups).intersection(inner_group)
            return func(ctx, bool(overlap), *args, **kwargs)
        return inner
    if forwarding:
        return outer_fwd
    if forwarding:
        return outer_fwd
    return outer_no_fwd

@overload
def have_any_group[**P, T, C: Context](forwarding: Literal[False] = False) -> Callable[[Callable[Concatenate[C, bool, P], T]], Callable[Concatenate[C, list[str], P], T | None]]: ... # pyright: ignore[reportOverlappingOverload]

@overload
def have_any_group[**P, T, C: Context](forwarding: Literal[True] = False) -> Callable[[Callable[Concatenate[C, bool, list[str], P], T]], Callable[Concatenate[C, list[str], P], T | None]]: ... # pyright: ignore[reportArgumentType]


def have_any_group[**P, T, C: Context](forwarding: bool = False) -> Callable[[Callable[Concatenate[C, bool, list[str], P], T]], Callable[Concatenate[C, list[str], P], T | None]] | Callable[[Callable[Concatenate[C, bool, P], T]], Callable[Concatenate[C, list[str], P], T | None]]:
    def outer_fwd(func: Callable[Concatenate[C, bool, list[str], P], T]) -> Callable[Concatenate[C, list[str], P], T | None]:
        def inner(ctx: C, inner_group: list[str], *args: P.args, **kwargs: P.kwargs) -> T | None:
            return func(ctx, bool(inner_group),list(inner_group), *args, **kwargs)
        return inner
    
    def outer_no_fwd(func: Callable[Concatenate[C, bool, P], T]) -> Callable[Concatenate[C, list[str], P], T | None]:
        def inner(ctx: C, inner_group: list[str], *args: P.args, **kwargs: P.kwargs) -> T | None:
            return func(ctx, bool(inner_group), *args, **kwargs)
        return inner
    if forwarding:
        return outer_fwd
    if forwarding:
        return outer_fwd
    return outer_no_fwd

def consume_second[**P, A, B, T](func: Callable[Concatenate[A, P], T]) -> Callable[Concatenate[A, B, P], T]: # pyright: ignore[reportInvalidTypeVarUse]
    def inner(a: A, _: B, *args: P.args, **kwargs: P.kwargs) -> T:
        return func(a, *args, **kwargs)
    return inner

def duplicate_second[**P, A, B, T](func: Callable[Concatenate[A, B, B, P], T]) -> Callable[Concatenate[A, B, P], T]:
    def inner(a: A, b: B, *args: P.args, **kwargs: P.kwargs) -> T:
        return func(a, b, b, *args, **kwargs)
    return inner

def swap[**P, A, B, C, T](func: Callable[Concatenate[A, C, B, P], T]) -> Callable[Concatenate[A, B, C, P], T]:
    def inner(a: A, b: B, c: C, *args: P.args, **kwargs: P.kwargs) -> T:
        return func(a, c, b, *args, **kwargs)
    return inner