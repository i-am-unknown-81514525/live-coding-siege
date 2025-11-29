from dataclasses import dataclass
from threading import Lock
from typing import Literal, ClassVar
from abc import ABC, abstractmethod
from importlib import import_module
from base import Client
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
class GameInstance[T]:
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
    client: Client[T]


class LiveModuleBase[T](ABC):
    BOUND: ClassVar[tuple[int, int]] = (300, 1200)

    def __init__(self, instance: GameInstance[T]):
        self._instance = instance
        super().__init__()

    @abstractmethod
    def on_create(self) -> None:
        pass

    @abstractmethod
    def on_end(self) -> None:
        pass

    @abstractmethod
    def on_restart(self) -> None:
        pass

    @abstractmethod
    def on_join(self, user_id: str) -> None:
        pass

    @abstractmethod
    def on_leave(self, user_id: str) -> None:
        pass

    @abstractmethod
    def on_pick(self, user_id: str) -> None:
        pass

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
