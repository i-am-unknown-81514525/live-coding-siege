from live.base import LiveModuleBase, GameInstance

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
        raise NotImplementedError

    def get_tickets(self, users: list[str]) -> dict[str, int]:
        raise NotImplementedError

    def refresh_tickets(self, users: list[str]) -> dict[str, int]:
        raise NotImplementedError



def get_module(instance: GameInstance) -> LiveModuleBase:
    return Hackatime(instance)