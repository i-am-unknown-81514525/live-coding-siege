from collections.abc import Callable
from schema.message import MessageEvent
from schema.interactive import BlockActionEvent
from schema.huddle import HuddleChange, HuddleState
from slack_sdk.web import WebClient
import threading
from typing import Any

MESSAGE_HANDLERS: dict[str, list[Callable[[MessageEvent, WebClient], Any]]] = {}
ACTION_HANDLERS: dict[str, list[Callable[[BlockActionEvent, WebClient], Any]]] = {}
HUDDLE_HANDLERS: dict[HuddleState, list[Callable[[HuddleChange, WebClient], Any]]] = {}

def msg_listen[A: Callable](message_key: str) -> Callable[[A], A]:
    """
    A decorator factory that registers a function to handle a specific message key.

    Args:
        message_key: The key for the message that the decorated function will handle.
    """
    if not isinstance(message_key, str):
        raise TypeError("The message_key for @msg_listen must be a string.")

    def decorator[F: Callable[[MessageEvent, WebClient], Any]](func: F) -> F:
        """The actual decorator that performs the registration."""
        if MESSAGE_HANDLERS.get(message_key) is None:
            MESSAGE_HANDLERS[message_key] = []
        MESSAGE_HANDLERS[message_key].append(func)
        return func
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

def message_dispatch(event: MessageEvent, client: WebClient) -> None:
    """
    Dispatches the event to handlers whose key the message text starts with.
    Each handler is run in a separate thread.
    """
    # A regular message has its content in `message_data`
    if not event.message or event.message.text is None:
        return

    message_text = event.message.text

    for key, handlers in MESSAGE_HANDLERS.items():
        if message_text.startswith(key):
            for handler in handlers:
                thread = threading.Thread(target=handler, args=(event, client))
                thread.start()

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
