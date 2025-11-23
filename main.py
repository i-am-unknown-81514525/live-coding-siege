import logging
import os
from threading import Thread, Event

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.client import BaseSocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

import live.db as db
from reg import (
    SlashContext,
    action_dispatch,
    huddle_dispatch,
    message_dispatch,
    slash_dispatch,
    slash_listen,
    DESCRIPTION,
    description,
    Context,
    smart_msg_listen
)
from schema.base import Recv
from schema.huddle import HuddleChange
from schema.interactive import BlockActionEvent
from schema.message import MessageEvent
from schema.slash_cmd import CommandEvent
import live.server as server, siege.core as core, siege.remind as remind
import utils
from types import ModuleType
from importlib import import_module

load_dotenv()

START_MODULE = [
    "live.server",
    "siege.core",
    "siege.remind",
    "live.live"
]
LOAD_MODULE = [
    "siege.cmd",
    "live.live"
]

all_module: dict[str, ModuleType] = {}

@smart_msg_listen("live.helps")
@smart_msg_listen("siege.helps")
@slash_listen("/help")
@description("/help <prefix>?", "Help command to hopefully answer your random question?")
@utils.get_group
@utils.filter_allowed
@utils.have_any_group()
def help(ctx: Context, public: bool):
    items = []
    for cmd, description in DESCRIPTION.items():
        if cmd.startswith(ctx.value):
            items.append(f"`{cmd}` - {description}")
    message = f"*Command list{ f" with prefix \"{ctx.value}\"" if ctx.value else "" }*\n" + ("\n".join(items) or "No command exist with the given prefix")
    if public:
        ctx.public_send(text=message)
    else:
        ctx.private_send(text=message)

# Cmd load
import siege.cmd as cmd
import live.live as live

def process_message(client: BaseSocketModeClient, req: SocketModeRequest):
    response = SocketModeResponse(envelope_id=req.envelope_id)
    client.send_socket_mode_response(response)
    with open("event.log", "a") as f:
        f.write(f"{req.type} {str(req.payload)}\n")
    event: Recv
    # Check if the event is a message and not from a bot
    if req.type == "events_api":
        event_payload = req.payload.get("event", {})
        event_type = event_payload.get("type")

        if event_type == "message" and "bot_id" not in event_payload:
            event = MessageEvent.parse(req.payload)
            message_dispatch(event, client.web_client)

        elif event_type == "user_huddle_changed":
            event = HuddleChange.parse(req.payload)
            huddle_dispatch(event, client.web_client)

    elif req.type == "interactive" and req.payload.get("type") == "block_actions":
        event = BlockActionEvent.parse(req.payload)
        action_dispatch(event, client.web_client)

    elif req.type == "slash_commands":
        event = CommandEvent.parse(req.payload)
        ctx = SlashContext(event, client.web_client)
        slash_dispatch(ctx)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db.init_db()
    client = SocketModeClient(
        app_token=os.environ["SLACK_APP_LEVEL_TOKEN"],
        web_client=WebClient(token=os.environ["SLACK_BOT_OAUTH_TOKEN"]),
    )
    for module_name in START_MODULE:
        try:
            module = import_module(module_name)
            all_module[module_name] = module
            module.start(client)
        except Exception as e:
            logging.error(f"Failed to load start_module {module_name}:", exc_info=True)
    for module_name in LOAD_MODULE:
        try:
            module = import_module(module_name)
            all_module[module_name] = module
        except Exception as e:
            logging.error(f"Failed to load load_module {module_name}:", exc_info=True)
    try:
        client.socket_mode_request_listeners.append(process_message)
        print("Bot is listening for messages...")
        client.connect()
        while True:
            try:
                Event().wait()
            except KeyboardInterrupt:
                break
            except Exception as e:
                logging.error(f"Uncaught exception:", exc_info=True)
    except Exception as e:
        logging.error(f"Failed to start SocketModeClient:", exc_info=True)