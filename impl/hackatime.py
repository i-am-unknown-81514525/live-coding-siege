from live.base import LiveModuleBase, GameInstance
from hackatime.api import fetch_hackatime_stats
from hackatime.db import append_game, get_game_start_hours


BASE = 10
HOUR_PER_TICKET = 0.1

class Hackatime(LiveModuleBase):
    BOUND = (300, 1200)
    CAN_OPTIN = False

    def on_create(self) -> None:
        return None

    def on_end(self) -> None:
        return None

    def on_restart(self) -> None:
        return None

    def on_join(self, user_id: str) -> None:
        return None

    def on_leave(self, user_id: str) -> None:
        return None

    def on_pick(self, user_id: str) -> None:
        return None
    
    def get_ticket(self, user: str) -> int:
        stats = fetch_hackatime_stats(user)
        if not stats:
            return 0
        append_game(user, self._instance.game_id, stats.stats.total_seconds / 3600)
        hours = get_game_start_hours(user, self._instance.game_id)
        if not hours:
            return 0
        return BASE + int(round((stats.stats.total_seconds / 3600 - hours)/HOUR_PER_TICKET, 0))

    def get_tickets(self, users: list[str]) -> dict[str, int]:
        return {user_id: self.get_ticket(user_id) for user_id in users}

    def refresh_tickets(self, users: list[str]) -> dict[str, int]:
        return self.get_tickets(users)


def get_module(instance: GameInstance) -> LiveModuleBase:
    return Hackatime(instance)