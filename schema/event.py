from dataclasses import dataclass
from enum import StrEnum

@dataclass(frozen=True)
class Event:
    pass

class EventEnum(StrEnum):
    HUDDLE_CHANGED = "user_huddle_changed"