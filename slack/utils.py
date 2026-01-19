from collections.abc import Callable
from typing import Concatenate, overload, Literal
from base import Context
import re
from functools import partial

# @overload
# def private_on_interaction[**P, T]() -> Callable[ # pyright: ignore[reportOverlappingOverload]
#     [Callable[Concatenate[InteractionContext, Literal[False], P], T]],
#     Callable[Concatenate[InteractionContext, bool, P], T],
# ]: ...
    
# @overload
# def private_on_interaction[**P, T, C: Context, B: Literal[True] | Literal[False]]() -> Callable[ # pyright: ignore[reportOverlappingOverload]
#     [Callable[Concatenate[C, B, P], T]],
#     Callable[Concatenate[C, B, P], T],
# ]: ...

def private_on_interaction[**P, T, C: Context]() -> Callable[ # pyright: ignore[reportInconsistentOverload]
    [Callable[Concatenate[C, bool, P], T]],
    Callable[Concatenate[C, bool, P], T],
]:
    def outer(
        func: Callable[Concatenate[C, bool, P], T],
    ) -> Callable[Concatenate[C, bool, P], T]:
        def inner(
            ctx: C, public: bool, *args: P.args, **kwargs: P.kwargs
        ) -> T:
            from slack.reg import InteractionContext
            return func(
                ctx, public and not isinstance(ctx, InteractionContext),*args, **kwargs
            )

        return inner

    return outer

def strip_ping(content: re.Match[str]) -> str:
    return f"[stripped: {content.group(0).strip().removeprefix("<").removesuffix(">")}]"

def strip_if_not_match(allowed: list[str], content: re.Match[str]) -> str:
    v = content.group(0)
    stripped = strip_ping(content)
    if stripped in allowed:
        return v
    return stripped


def filter_ping(content: str, allowed_user: bool | list[str] = False) -> str:
    if not allowed_user:
        content = re.sub("<@U[A-Z0-9]{9}>", strip_ping, content)
    elif isinstance(allowed_user, list):
        content = re.sub(f"<@({'|'.join(allowed_user)})>", partial(strip_if_not_match, allowed_user), content)
    ori = ""
    while ori != content:
        ori = content
        content = re.sub("<!channel(\\|[^>\\|\r\n]*)?>", "@channel", content)
        content = re.sub("<!here(\\|[^>\\|\r\n]*)?>", "@here", content)
    return content