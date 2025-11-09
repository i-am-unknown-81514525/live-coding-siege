from .base import Event, SlackID
from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True)
class CommandEvent(Event):
    token: str
    team_id: SlackID
    team_domain: str
    channel_id: SlackID
    channel_name: str
    user_id: SlackID
    user_name: str
    command: str
    text: str
    api_app_id: SlackID
    is_enterprise_install: bool
    response_url: str
    trigger_id: str

    @classmethod
    def parse(cls, data: dict) -> Self:
        return cls(
            token=data["token"],
            team_id=data["team_id"],
            team_domain=data["team_domain"],
            channel_id=data["channel_id"],
            channel_name=data["channel_name"],
            user_id=data["user_id"],
            user_name=data["user_name"],
            command=data["command"],
            text=data["text"],
            api_app_id=data["api_app_id"],
            is_enterprise_install=data["is_enterprise_install"] == "true",
            response_url=data["response_url"],
            trigger_id=data["trigger_id"],
        )
