from .base import Event, SlackID
from dataclasses import dataclass

@dataclass(frozen=True)
class CommandEvent(Event):
    team_id: SlackID
