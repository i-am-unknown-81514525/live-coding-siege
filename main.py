import logging
import os
from threading import Thread, Event

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.client import BaseSocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

import db
from reg import SlashContext, action_dispatch, huddle_dispatch, message_dispatch, slash_dispatch
from schema.base import Recv
from schema.huddle import HuddleChange
from schema.interactive import BlockActionEvent
from schema.message import MessageEvent
from schema.slash_cmd import CommandEvent
from server import start_server

import live
import siege_cmd


load_dotenv()


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
    thread = Thread(target=start_server)
    thread.start()
    client = SocketModeClient(
        app_token=os.environ["SLACK_APP_LEVEL_TOKEN"],
        web_client=WebClient(token=os.environ["SLACK_BOT_OAUTH_TOKEN"]),
    )
    live.load_active_timers(client.web_client)
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
