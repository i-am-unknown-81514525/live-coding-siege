import threading
from typing import Any, Callable, Sequence, TYPE_CHECKING

from slack_sdk.models.blocks import Block
from base import Client, Context
from irc.schema.event import Event
from dataclasses import dataclass
from schema.file import Attachment, PendingFile, UploadedFile
from slack.reg import MessageContext

MESSAGE_HANDLERS: dict[str, list[Callable[["IRCContext"], Any]]] = {}

if TYPE_CHECKING:
    from irc.client import IRCClient

@dataclass
class IRCContext(Context["IRCClient"]):
    event: Event
    client: "IRCClient"

    @property
    def value(self) -> str:
        if self.event.trailing is not None:
            return self.event.trailing.split(" ", 1)[1] if " " in self.event.trailing else self.event.trailing
        return ""
    
    @property
    def message_ts(self) -> str | None:
        return None

    @property
    def thread_ts(self) -> str | None:
        return None
    
    @property
    def channel_id(self) -> str:
        if len(self.event.params) >= 1 and self.event.params[0] != self.client.nickname:
            return self.event.params[0]
        return self.event.prefix or ""

    @property
    def cmd(self) -> str: 
        if self.event.trailing is not None:
            return self.event.trailing.split(" ")[0]
        return ""

    @property
    def action_namespace(self) -> str: 
        return f"irc_cmd:{self.cmd}"

    @property
    def list_namespace(self) -> list[str]:
        namespaces = [
            self.action_namespace,
            f"irc_channel:{self.channel_id}",
        ]
        return namespaces
    
    @property
    def author_id(self) -> str:
        return self.event.prefix or ""

    def public_send(self, always_thread: bool = False, files: list[PendingFile | UploadedFile] | None = None, *, text: str | None = None, as_user: bool | None = None, attachments: str | Sequence[dict[str, Any] | Attachment] | None = None, blocks: str | Sequence[dict[str, Any] | Block] | None = None, thread_ts: str | None = None, icon_emoji: str | None = None, icon_url: str | None = None, link_names: bool | None = None, username: str | None = None, parse: str | None = None, **kwargs) -> Any:
        return self.client.send_message(
            channel=self.channel_id,
            text=text or "Cannot render",)

    def private_send(self, always_thread: bool = False, files: list[PendingFile | UploadedFile] | None = None, *, text: str | None = None, as_user: bool | None = None, attachments: str | Sequence[dict[str, Any] | Attachment] | None = None, blocks: str | Sequence[dict[str, Any] | Block] | None = None, thread_ts: str | None = None, icon_emoji: str | None = None, icon_url: str | None = None, link_names: bool | None = None, username: str | None = None, parse: str | None = None, **kwargs) -> Any:
        return self.client.send_message(
            channel=self.channel_id,
            text=text or "Cannot render",)



def irc_msg_listen[A: Callable[[IRCContext], Any]](cmd: str) -> Callable[[A], A]:
    """Decorator to register an IRC message handler for a specific command.
    
    Args:
        cmd (str): The IRC command to listen for.
    """
    def decorator[F: Callable[[IRCContext], Any]](func: F) -> F:
        if cmd not in MESSAGE_HANDLERS:
            MESSAGE_HANDLERS[cmd] = []
        MESSAGE_HANDLERS[cmd].append(func)
        return func
    return decorator
    
def message_dispatch(event: Event, client: "IRCClient") -> None:
    """
    Dispatches the event to handlers whose key the message text starts with.
    Each handler is run in a separate thread.
    """
    for key, handlers in MESSAGE_HANDLERS.items():
        for handler in handlers:
            if (    
                event.trailing
                and (
                    event.trailing.startswith(key)
                    or event.trailing.strip() == key.strip()
                )
                
            ):
                thread = threading.Thread(target=handler, args=(IRCContext(event=event, client=client),))
                thread.start()