from collections.abc import Callable
from schema.message import MessageEvent
from schema.interactive import BlockActionEvent
from schema.huddle import HuddleChange, HuddleState
from slack_sdk.web import WebClient
import threading
from typing import Any, Sequence, overload
from dataclasses import dataclass
from abc import ABC, abstractmethod

from slack_sdk.models.blocks import Block
from slack_sdk.models.attachments import Attachment
from slack_sdk.webhook.client import WebhookClient

from schema.slash_cmd import CommandEvent

MESSAGE_HANDLERS: dict[str, list[Callable[[MessageEvent, WebClient], Any]]] = {}
ACTION_HANDLERS: dict[str, list[Callable[[BlockActionEvent, WebClient], Any]]] = {}
ACTION_PREFIX_HANDLERS: dict[
    str, list[Callable[[BlockActionEvent, WebClient], Any]]
] = {}
HUDDLE_HANDLERS: dict[HuddleState, list[Callable[[HuddleChange, WebClient], Any]]] = {}
SLASH_HANDLER: dict[str, list[Callable[["SlashContext"], Any]]] = {}
DESCRIPTION: dict[str, str] = {}

# def msg_listen[A: Callable](
#     message_key: str, is_subtype: bool = False
# ) -> Callable[[A], A]:
#     """
#     A decorator factory that registers a function to handle a specific message key.

#     Args:
#         message_key: The key for the message that the decorated function will handle.
#         is_subtype: If True, matches against the message subtype instead of the text content.
#     """
#     if not isinstance(message_key, str):
#         raise TypeError("The message_key for @msg_listen must be a string.")

#     def decorator[F: Callable[[MessageEvent, WebClient], Any]](func: F) -> F:
#         """The actual decorator that performs the registration."""
#         handlers = MESSAGE_HANDLERS.setdefault(message_key, [])
#         handlers.append(func)
#         setattr(func, "_is_subtype_handler", is_subtype)
#         return func  # type: ignore

#     return decorator


class Context(ABC):
    client: WebClient

    @property
    def value(self) -> str: ...

    @property
    def author_id(self) -> str: ...
    @property
    def message_ts(self) -> str | None: ...
    @property
    def thread_ts(self) -> str | None: ...
    @property
    def channel_id(self) -> str: ...

    @property
    def cmd(self) -> str: ...

    @property
    def action_namespace(self) -> str: ...

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


@dataclass
class MessageContext(Context):
    event: MessageEvent
    client: WebClient

    @property
    def author_id(self) -> str:
        return self.event.message.user

    @property
    def message_ts(self) -> str | None:
        return self.event.message.ts

    @property
    def thread_ts(self) -> str | None:
        return self.event.message.thread_ts

    @property
    def channel_id(self) -> str:
        return self.event.channel

    @property
    def value(self) -> str:
        r = self.event.message.text.split(" ", 1)
        if len(r) > 1:
            return r[1].strip()
        return ""
    
    @property
    def cmd(self) -> str:
        return self.event.message.text.split(" ")[0].strip()
    
    @property
    def action_namespace(self) -> str:
        return f"cmd:{self.cmd}"

    @overload
    def private_send(  # pyright: ignore[reportInconsistentOverload]
        self,
        always_thread: bool = False,
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

    def private_send[**P](
        self, always_thread: bool = False, *args: P.args, **kwargs: P.kwargs
    ):
        thread_ts = self.thread_ts
        if thread_ts is None and always_thread and self.message_ts:
            thread_ts = self.message_ts
        return self.client.chat_postEphemeral(
            user=self.author_id,
            channel=self.channel_id,
            thread_ts=thread_ts,
            *args,
            **kwargs,
        )

    @overload
    def public_send(  # pyright: ignore[reportInconsistentOverload]
        self,
        always_thread: bool = False,
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

    def public_send[**P](
        self, always_thread: bool = False, *args: P.args, **kwargs: P.kwargs
    ):
        thread_ts = self.thread_ts
        if thread_ts is None and always_thread and self.message_ts:
            thread_ts = self.message_ts
        return self.client.chat_postMessage(
            channel=self.channel_id, thread_ts=thread_ts, *args, **kwargs
        )


@dataclass
class SlashContext(Context):
    event: CommandEvent
    client: WebClient

    @property
    def webhook_client(self) -> WebhookClient:
        return WebhookClient(self.event.response_url)

    @property
    def author_id(self) -> str:
        return self.event.user_id

    @property
    def message_ts(self) -> str | None:
        return None  # Wait wtf

    @property
    def thread_ts(self) -> str | None:
        return None

    @property
    def channel_id(self) -> str:
        return self.event.channel_id

    @property
    def value(self) -> str:
        return self.event.text.strip()
    
    @property
    def cmd(self) -> str:
        return self.event.command.strip()
    
    @property
    def action_namespace(self) -> str:
        return f"slash:{self.cmd}"

    @overload
    def private_send(  # pyright: ignore[reportInconsistentOverload]
        self,
        always_thread: bool = False,
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

    def private_send[**P](
        self, always_thread: bool = False, *args: P.args, **kwargs: P.kwargs
    ):
        thread_ts = self.thread_ts
        if thread_ts is None and always_thread and self.message_ts:
            thread_ts = self.message_ts
        return self.webhook_client.send(
            response_type="ephemeral",
            *args,
            **kwargs,
        )

    @overload
    def public_send(  # pyright: ignore[reportInconsistentOverload]
        self,
        always_thread: bool = False,
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

    def public_send[**P](
        self, always_thread: bool = False, *args: P.args, **kwargs: P.kwargs
    ):
        thread_ts = self.thread_ts
        if thread_ts is None and always_thread and self.message_ts:
            thread_ts = self.message_ts
        return self.webhook_client.send(response_type="in_channel", *args, **kwargs)

@dataclass
class InteractionContext(Context):
    event: BlockActionEvent
    client: WebClient

    @property
    def author_id(self) -> str:
        return self.event.user.id
    
    @property
    def value(self) -> str:
        return self.event.actions[0].value or ""
    
    @property
    def message_ts(self) -> str | None:
        return self.event.container.message_ts
    
    @property
    def thread_ts(self) -> str | None:
        return self.event.container.thread_ts
    
    @property
    def channel_id(self) -> str:
        return self.event.container.channel_id
    
    @property
    def cmd(self) -> str:
        return self.event.actions[0].action_id
    
    @property
    def action_namespace(self) -> str:
        return f"interation:{self.cmd}"
    
    @overload
    def private_send(  # pyright: ignore[reportInconsistentOverload]
        self,
        always_thread: bool = False,
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

    def private_send[**P](
        self, always_thread: bool = False, *args: P.args, **kwargs: P.kwargs
    ):
        thread_ts = self.thread_ts
        if thread_ts is None and always_thread and self.message_ts:
            thread_ts = self.message_ts
        return self.client.chat_postEphemeral(
            user=self.author_id,
            channel=self.channel_id,
            thread_ts=thread_ts,
            *args,
            **kwargs,
        )

    @overload
    def public_send(  # pyright: ignore[reportInconsistentOverload]
        self,
        always_thread: bool = False,
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

    def public_send[**P](
        self, always_thread: bool = False, *args: P.args, **kwargs: P.kwargs
    ):
        thread_ts = self.thread_ts
        if thread_ts is None and always_thread and self.message_ts:
            thread_ts = self.message_ts
        return self.client.chat_postMessage(
            channel=self.channel_id, thread_ts=thread_ts, *args, **kwargs
        )
    


def smart_msg_listen[A: Callable](
    message_key: str, is_subtype: bool = False
) -> Callable[[A], A]:
    """
    A decorator factory that registers a function to handle a specific message key.

    Args:
        message_key: The key for the message that the decorated function will handle.
        is_subtype: If True, matches against the message subtype instead of the text content.
    """
    if not isinstance(message_key, str):
        raise TypeError("The message_key for @smart_msg_listen must be a string.")

    def decorator[F: Callable[[MessageContext], Any]](func: F) -> F:
        """The actual decorator that performs the registration."""
        handlers = MESSAGE_HANDLERS.setdefault(message_key, [])

        def inner(event: MessageEvent, client: WebClient):
            # TODO: Handle <http://siege.lb|siege.lb>
            ctx = MessageContext(event, client)
            return func(ctx)

        handlers.append(inner)
        setattr(func, "_is_subtype_handler", is_subtype)
        return func  # type: ignore

    return decorator


def action_listen[A: Callable](action_id: str) -> Callable[[A], A]:
    """
    A decorator factory that registers a function to handle a specific block action_id.

    Args:
        action_id: The action_id from the block element that this function will handle.
    """
    if not isinstance(action_id, str):
        raise TypeError("The action_id for @action_listen must be a string.")

    def decorator[F: Callable[[BlockActionEvent, WebClient], Any]](func: F) -> F:
        """The actual decorator that performs the registration."""
        if ACTION_HANDLERS.get(action_id) is None:
            ACTION_HANDLERS[action_id] = []
        ACTION_HANDLERS[action_id].append(func)
        return func

    return decorator


def action_prefix_listen[A: Callable](action_id_prefix: str) -> Callable[[A], A]:
    """
    A decorator factory that registers a function to handle block actions
    where the action_id starts with a specific prefix.

    Args:
        action_id_prefix: The prefix for the action_id that this function will handle.
    """
    if not isinstance(action_id_prefix, str):
        raise TypeError(
            "The action_id_prefix for @action_prefix_listen must be a string."
        )

    def decorator[F: Callable[[BlockActionEvent, WebClient], Any]](func: F) -> F:
        """The actual decorator that performs the registration."""
        if ACTION_PREFIX_HANDLERS.get(action_id_prefix) is None:
            ACTION_PREFIX_HANDLERS[action_id_prefix] = []
        ACTION_PREFIX_HANDLERS[action_id_prefix].append(func)
        return func

    return decorator

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

def huddle_listen[A: Callable](state: HuddleState) -> Callable[[A], A]:
    """
    A decorator factory that registers a function to handle a user's huddle state change.

    Args:
        state: The HuddleState (IN_HUDDLE or NOT_IN_HUDDLE) to listen for.
    """
    if not isinstance(state, HuddleState):
        raise TypeError("The state for @huddle_listen must be a HuddleState enum.")

    def decorator[F: Callable[[HuddleChange, WebClient], Any]](func: F) -> F:
        """The actual decorator that performs the registration."""
        if HUDDLE_HANDLERS.get(state) is None:
            HUDDLE_HANDLERS[state] = []
        HUDDLE_HANDLERS[state].append(func)
        return func

    return decorator


def slash_listen[A: Callable](slash_cmd: str) -> Callable[[A], A]:
    """
    A decorator factory that registers a function to handle a slash command.

    Args:
        slash_cmd: The slash command to listen for.
    """
    if not isinstance(slash_cmd, str):
        raise TypeError("The slash_cmd for @slash_listen must be a string.")

    def decorator[F: Callable[[SlashContext], Any]](func: F) -> F:
        if SLASH_HANDLER.get(slash_cmd) is None:
            SLASH_HANDLER[slash_cmd] = []
        SLASH_HANDLER[slash_cmd].append(func)
        return func

    return decorator


def message_dispatch(event: MessageEvent, client: WebClient) -> None:
    """
    Dispatches the event to handlers whose key the message text starts with.
    Each handler is run in a separate thread.
    """
    for key, handlers in MESSAGE_HANDLERS.items():
        for handler in handlers:
            is_subtype_handler = getattr(handler, "_is_subtype_handler", False)

            # Dispatch to subtype handlers
            if is_subtype_handler and event.subtype == key:
                thread = threading.Thread(target=handler, args=(event, client))
                thread.start()
                continue

            # Dispatch to text-based command handlers
            if (
                not is_subtype_handler
                and event.message
                and event.message.text
                and event.message.text.startswith(key)
            ):
                thread = threading.Thread(target=handler, args=(event, client))
                thread.start()

            # TODO: Handle <http://siege.lb|siege.lb>


def action_dispatch(event: BlockActionEvent, client: WebClient) -> None:
    """
    Dispatches the block action event to handlers based on action_id.
    Each handler is run in a separate thread.
    """
    for action in event.actions:
        action_id = action.action_id
        if action_id in ACTION_HANDLERS:
            handlers = ACTION_HANDLERS[action_id]
            for handler in handlers:
                # Pass the entire event to the handler
                thread = threading.Thread(target=handler, args=(event, client))
                thread.start()

        for prefix, handlers in ACTION_PREFIX_HANDLERS.items():
            if action_id.startswith(prefix):
                for handler in handlers:
                    thread = threading.Thread(target=handler, args=(event, client))
                    thread.start()


def huddle_dispatch(event: HuddleChange, client: WebClient) -> None:
    """
    Dispatches the huddle change event to handlers based on the user's new state.
    Each handler is run in a separate thread.
    """
    state = event.huddle_state
    if state in HUDDLE_HANDLERS:
        handlers = HUDDLE_HANDLERS[state]
        for handler in handlers:
            thread = threading.Thread(target=handler, args=(event, client))
            thread.start()


def slash_dispatch(event: SlashContext) -> None:
    """
    Dispatches the slash command event to handlers based on the command name.
    Each handler is run in a separate thread.
    """
    for handler in SLASH_HANDLER.get(event.event.command, []):
        thread = threading.Thread(target=handler, args=(event,))
        thread.start()
