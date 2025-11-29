from base import Client
from slack_sdk.socket_mode.client import BaseSocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
from threading import Event
import logging
from slack.reg import SlashContext, message_dispatch, huddle_dispatch, action_dispatch, slash_dispatch
from schema.base import Recv
from schema.message import MessageEvent
from schema.huddle import HuddleChange
from schema.interactive import BlockActionEvent
from schema.slash_cmd import CommandEvent


def process_message(client: "SlackClient", req: SocketModeRequest):
    response = SocketModeResponse(envelope_id=req.envelope_id)
    client.client.send_socket_mode_response(response)
    with open("event.log", "a") as f:
        f.write(f"{req.type} {str(req.payload)}\n")
    event: Recv
    # Check if the event is a message and not from a bot
    if req.type == "events_api":
        event_payload = req.payload.get("event", {})
        event_type = event_payload.get("type")

        if event_type == "message" and "bot_id" not in event_payload:
            event: MessageEvent = MessageEvent.parse(req.payload)
            message_dispatch(event, client)

        elif event_type == "user_huddle_changed":
            event: HuddleChange = HuddleChange.parse(req.payload)
            huddle_dispatch(event, client)

    elif req.type == "interactive" and req.payload.get("type") == "block_actions":
        event: BlockActionEvent = BlockActionEvent.parse(req.payload)
        action_dispatch(event, client)
    elif req.type == "slash_commands":
        event: CommandEvent = CommandEvent.parse(req.payload)
        ctx = SlashContext(event, client)
        slash_dispatch(ctx)


class SlackClient(Client[BaseSocketModeClient]):
    def start(self):
        client = self.client
        try:
            client.socket_mode_request_listeners.append(self.wrapper)
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
    
    def wrapper(self, _: BaseSocketModeClient, req: SocketModeRequest):
        process_message(self, req)