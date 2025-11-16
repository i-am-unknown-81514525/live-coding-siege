from dataclasses import dataclass
from threading import Lock
from typing import Literal

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
    game_lock: Lock
    channel_id: str
    thread_ts: str
    turns: list[Turns]
    managers: list[str]
    participants: list[str]

    

