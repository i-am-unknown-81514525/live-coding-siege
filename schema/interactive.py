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
    message_ts: Arrow

    @classmethod
    def parse(cls, data: dict) -> Self:
        return cls(
            type=data["type"],
            channel_id=data["channel_id"],
            message_ts=Arrow.fromtimestamp(float(data["message_ts"])),
        )

@dataclass(frozen=True)
class Action:
    type: str
    action_id: str
    block_id: str
    action_ts: Arrow

    @classmethod
    def parse(cls, data: dict) -> Self:
        return cls(
            type=data["type"],
            action_id=data["action_id"],
            block_id=data["block_id"],
            action_ts=Arrow.fromtimestamp(float(data["action_ts"])),
        )

@dataclass(frozen=True)
class BlockActionEvent(Recv):
    """Represents a user interaction with a block element (e.g., clicking a button)."""
    user: InteractionUser
    api_app_id: str
    container: Container
    trigger_id: str
    response_url: str
    message: MessageData
    actions: list[Action]

    @classmethod
    def parse(cls, data: dict) -> Self:
        return cls(
            user=InteractionUser.parse(data["user"]),
            api_app_id=data["api_app_id"],
            container=Container.parse(data["container"]),
            trigger_id=data["trigger_id"],
            response_url=data["response_url"],
            # The 'message' object in a block action is a full message payload
            message=MessageData.parse(data["message"]),
            actions=[Action.parse(action) for action in data.get("actions", [])],
        )