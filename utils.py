from collections.abc import Callable
from typing import Concatenate

from api import get_all_projs
import db
from reg import Context
from typing import Any


def guess_week() -> int:
    projs = get_all_projs()
    max_week_num = max(projs, key=lambda p: p.week).week
    return max_week_num

def require_game_manager[**P, T, C: Context](func: Callable[Concatenate[C, int, P], T]) -> Callable[Concatenate[C, P], T | None]:
    def inner(ctx: C, *args: P.args, **kwargs: P.kwargs) -> T | None:
        if not db.has_game_manager(ctx.author_id):
            return None
        game_id = db.get_game_mgr_active_game(ctx.author_id)
        if game_id is None:
            return None
        return func(ctx, game_id, *args, **kwargs)
    return inner


