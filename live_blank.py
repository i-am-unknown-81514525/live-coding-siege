from live_base import LiveModuleBase, GameInstance

class Blank(LiveModuleBase):
    def __init__(self, instance: GameInstance):
        super().__init__(instance)

    def get_ticket(self, user: str) -> int:
        return 1

    def get_tickets(self, users: list[str]) -> dict[str, int]:
        return {user: 1 for user in users}

    def refresh_tickets(self, users: list[str]) -> dict[str, int]:
        return {user: 1 for user in users}

def get_module(instance: GameInstance) -> LiveModuleBase:
    return Blank(instance)