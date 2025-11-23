import logging
from live.base import GameInstance, LiveModuleBase
from live.live import push_ticket_update_ws
from siege.core import (
    fetch_all_user_link,
    get_user_id_from_slack,
    get_user_ticket,
    push_link,
    push_proj,
)
from siege import utils, api
from siege.schema.siege import SiegeProject


class Siege(LiveModuleBase):
    def __init__(self, instance: GameInstance):
        for participant in instance.participants:
            user_id = get_user_id_from_slack(participant)
            if user_id is not None:
                push_link(instance.game_id, user_id)
        super().__init__(instance)

    def get_ticket(self, user: str) -> int:
        week_num = utils.guess_week()
        return get_user_ticket(
            self._instance.game_id, user, week_num, self._instance.start_time
        )

    def get_tickets(self, users: list[str]) -> dict[str, int]:
        week_num = utils.guess_week()
        return {
            user: get_user_ticket(
                self._instance.game_id, user, week_num, self._instance.start_time
            )
            for user in users
        }

    def refresh_tickets(self, users: list[str]) -> dict[str, int]:
        projs: list[SiegeProject] = []
        try:
            projs = api.get_all_projs()
            push_proj(projs)
        except Exception as e:
            logging.warning(f"Faile to fetch project", exc_info=True)
        try:
            game_req_update = fetch_all_user_link(
                list(set(proj.user.id for proj in projs))
            )
            for game_id in game_req_update:
                try:
                    push_ticket_update_ws(game_id)
                except Exception as e:
                    logging.info(f"Faile to push update on game", exc_info=True)
        except Exception as e:
            logging.warning(f"Faile to push update on game", exc_info=True)
        return self.get_tickets(users)

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


def get_module(instance: GameInstance) -> Siege:
    return Siege(instance)
