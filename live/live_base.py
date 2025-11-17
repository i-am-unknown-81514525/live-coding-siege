from dataclasses import dataclass
from threading import Lock
from typing import Literal
from abc import ABC, abstractmethod
from importlib import import_module
from config import get_config
from arrow import Arrow

@dataclass(frozen=True)
class Turns:
    used_id: str
    seq_id: int
    status: Literal["PENDING", "IN_PROGRESS", "FAILED", "COMPLETED"]
    time_start: float | None
    duration: float


@dataclass(frozen=True)
class GameInstance:
    game_id: int
    client_secret: str
    server_secret: str
    channel_id: str
    thread_ts: str
    turns: list[Turns]
    managers: list[str]
    participants: list[str]
    mode: str
    start_time: Arrow


class LiveModuleBase(ABC):
    def __init__(self, instance: GameInstance):
        self._instance = instance
        super().__init__()
    
    @abstractmethod
    def get_ticket(self, user: str) -> int: ...

    @abstractmethod
    def get_tickets(self, users: list[str]) -> dict[str, int]: ...

    @abstractmethod
    def refresh_tickets(self, users: list[str]) -> dict[str, int]: ...

def get_module(instance: GameInstance) -> LiveModuleBase:
    config = get_config()["bot"]["group"][instance.mode]
    module = import_module(config["module"])
    return getattr(module, "get_module")(instance)