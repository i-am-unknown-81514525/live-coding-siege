from collections.abc import Sequence, Callable
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING
from abc import ABC, abstractmethod
import threading

from schema.file import Attachment, PendingFile, UploadedFile
from slack_sdk.models.blocks import Block

if TYPE_CHECKING:
    import slack.client
    import irc.client

type CtxFn[C: Context, T] = Callable[[C], T]
DESCRIPTION: dict[str, str] = {}

def description[A: Callable](cmd: str, description: str) -> Callable[[A], A]:
    """
    Mark description for the command

    Args:
        cmd: Command
        description: The description for the command
    """
    DESCRIPTION[cmd] = description

    def decorator[F: Callable](func: F) -> F:
        return func

    return decorator


@dataclass
class ExecutionContext:
    slack_client: "slack.client.SlackClient"
    # irc_client: "irc.client.IRCClient"

class Client[T](ABC):
    def __init__(self, inner: T):
        self._client: T = inner

    @abstractmethod
    def start(self):
        ...
    
    @property
    def client(self) -> T:
        return self._client

    def start_threaded(self) -> threading.Thread:
        thread = threading.Thread(target=self.start)
        thread.start()
        return thread

class Context[T: Client](ABC):
    client: T

    @property
    @abstractmethod
    def value(self) -> str:
        raise NotImplementedError()

    @property
    @abstractmethod
    def author_id(self) -> str:
        raise NotImplementedError()

    @property
    @abstractmethod
    def message_ts(self) -> str | None:
        raise NotImplementedError()

    @property
    @abstractmethod
    def thread_ts(self) -> str | None:
        raise NotImplementedError()

    @property
    @abstractmethod
    def channel_id(self) -> str:
        raise NotImplementedError()

    
    @property
    @abstractmethod
    def cmd(self) -> str:
        raise NotImplementedError()

    @property
    @abstractmethod
    def action_namespace(self) -> str:
        raise NotImplementedError()

    @property
    def list_namespace(self) -> list[str]:
        namespaces = [
            self.action_namespace,
            f"channel:{self.channel_id}",
            f"author:{self.author_id}",
        ]
        if self.thread_ts:
            namespaces.append(f"thread:{self.thread_ts}")
        if self.message_ts:
            namespaces.append(f"message:{self.message_ts}")
        return namespaces

    def private_send(  # pyright: ignore[reportInconsistentOverload]
        self,
        always_thread: bool = False,
        files: list[PendingFile | UploadedFile] | None = None,
        *,
        text: str | None = None,
        as_user: bool | None = None,
        attachments: str | Sequence[dict[str, Any] | Attachment] | None = None,
        blocks: str | Sequence[dict[str, Any] | Block] | None = None,
        thread_ts: str | None = None,
        icon_emoji: str | None = None,
        icon_url: str | None = None,
        link_names: bool | None = None,
        username: str | None = None,
        parse: str | None = None,
        **kwargs,
    ) -> Any: ...

    def public_send(  # pyright: ignore[reportInconsistentOverload]
        self,
        always_thread: bool = False,
        files: list[PendingFile | UploadedFile] | None = None,
        *,
        text: str | None = None,
        as_user: bool | None = None,
        attachments: str | Sequence[dict[str, Any] | Attachment] | None = None,
        blocks: str | Sequence[dict[str, Any] | Block] | None = None,
        thread_ts: str | None = None,
        icon_emoji: str | None = None,
        icon_url: str | None = None,
        link_names: bool | None = None,
        username: str | None = None,
        parse: str | None = None,
        **kwargs,
    ) -> Any: ...