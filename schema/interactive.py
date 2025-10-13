from dataclasses import dataclass
from typing import Self
from arrow import Arrow
from .base import Recv, SlackID
from .message import MessageData

@dataclass(frozen=True)
class InteractionUser:
    id: SlackID
    username: str
    name: str
    team_id: SlackID

    @classmethod
    def parse(cls, data: dict) -> Self:
        return cls(
            id=data["id"],
            username=data["username"],
            name=data["name"],
            team_id=data["team_id"],
        )

@dataclass(frozen=True)
class Container:
    type: str
    channel_id: SlackID
    message_ts: str # Keep as string for API compatibility

    @classmethod
    def parse(cls, data: dict) -> Self:
        return cls(
            type=data["type"],
            channel_id=data["channel_id"],
            message_ts=data["message_ts"],
        )

@dataclass(frozen=True)
class Action:
    type: str
    action_id: str
    block_id: str
    action_ts: Arrow
    value: str | None = None

    @classmethod
    def parse(cls, data: dict) -> Self:
        return cls(
            type=data["type"],
            action_id=data["action_id"],
            block_id=data["block_id"],
            action_ts=Arrow.fromtimestamp(float(data["action_ts"])),
            value=data.get("value"),
        )

@dataclass(frozen=True)
class BlockActionEvent(Recv):
    user: InteractionUser
    api_app_id: str
    container: Container
    trigger_id: str
    response_url: str
    message: MessageData | None
    actions: list[Action]

    @classmethod
    def parse(cls, data: dict) -> Self:
        message_data = data.get("message")
        return cls(
            user=InteractionUser.parse(data["user"]),
            api_app_id=data["api_app_id"],
            container=Container.parse(data["container"]),
            trigger_id=data["trigger_id"],
            response_url=data["response_url"],
            message=MessageData.parse(message_data) if message_data else None,
            actions=[Action.parse(action) for action in data.get("actions", [])],
        )