import siege.core as siege
from live.base import GameInstance, LiveModuleBase
import arrow
from datetime import timedelta

class SiegeRedacted(LiveModuleBase):
    BOUND = (1200, 2400)
    def on_create(self) -> None:
        pass

    def on_end(self) -> None:
        pass

    def on_restart(self) -> None:
        pass

    def on_join(self, user_id: str) -> None:
        if len(self._instance.managers) == 1:
            self._instance.client.chat_postMessage(
                channel=self._instance.channel_id,
                thread_ts=self._instance.thread_ts,
                text=f"<@{user_id}> has joined and now the game can be resumed!")


    def on_leave(self, user_id: str) -> None:
        if len(self._instance.managers) == 0:
            self._instance.client.chat_postMessage(
                channel=self._instance.channel_id,
                thread_ts=self._instance.thread_ts,
                text=f"All managers have left. The game is now paused.")

    def on_pick(self, user_id: str) -> None:
        pass

    def get_ticket(self, user: str) -> int:
        user_id = siege.get_user_id_from_slack(user)
        if not user_id:
            return 0
        heartbeats = siege.retrieve_all_heartbeat_curr_proj_curr_week(user_id, 14, arrow.now() - timedelta(minutes=15))
        most_recent = max(heartbeats, key=lambda hb: hb.measurement_time.timestamp()) if heartbeats else None
        if not most_recent:
            return 0
        hours = most_recent.hours
        return 10 + int(round(hours * 10, 0))

    def get_tickets(self, users: list[str]) -> dict[str, int]:
        return {user: self.get_ticket(user) for user in users}

    def refresh_tickets(self, users: list[str]) -> dict[str, int]:
        siege.prox_get_all_projs()
        return {user: self.get_ticket(user) for user in users}

def get_module(instance: GameInstance) -> SiegeRedacted:
    return SiegeRedacted(instance)