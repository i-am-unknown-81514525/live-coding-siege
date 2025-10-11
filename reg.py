from collections.abc import Callable
from schema.message import MessageEvent
from slack_sdk.web import WebClient
import threading
from typing import Any

MESSAGE_HANDLERS: dict[str, list[Callable[[MessageEvent, WebClient], Any]]] = {}

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
