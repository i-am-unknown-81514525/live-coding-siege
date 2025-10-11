type SlackID = str
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

@dataclass(frozen=True)
class Recv:
    ...

@dataclass(frozen=True)
class Event(Recv):
    __EVENT__: ClassVar[str]

class EventEnum(StrEnum):
    HUDDLE_CHANGED = "user_huddle_changed"
    MESSAGE = "message"