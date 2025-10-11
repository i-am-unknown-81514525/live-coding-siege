import os, logging
from threading import Event as tEvent

from dotenv import load_dotenv
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.client import BaseSocketModeClient
from slack_sdk.web import WebClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

from schema.base import Event, Recv
from schema.message import MessageEvent
from schema.interactive import BlockActionEvent
from reg import message_dispatch, msg_listen
import blockkit

@msg_listen("live.test1")
def test_interactive(event: MessageEvent, client: WebClient):
    message_payload = (
        blockkit.Message(text="This is a test message with a button.") # Fallback text for notifications
        .add_block(
            blockkit.Section("test")
            .accessory(
                blockkit.Button("Test Button")
                .action_id("test_button")
            )
        )
    ).build()
    client.chat_postMessage(
        channel=event.channel, **message_payload
    )


load_dotenv()

# This function is called when a message is sent to a channel the bot is in
def process_message(client: BaseSocketModeClient, req: SocketModeRequest):
    # Acknowledge the event first
    response = SocketModeResponse(envelope_id=req.envelope_id)
    client.send_socket_mode_response(response)
    print(req.type, req.payload)
    with open("event.log", "a") as f:
        f.write(f"{req.type} {str(req.payload)}\n")
    event: Recv
    # Check if the event is a message and not from a bot
    if req.type == "events_api":
        if req.payload["event"]["type"] == "message" and "bot_id" not in req.payload["event"]:
            
            event = MessageEvent.parse(req.payload)
            print(event)
            message_dispatch(event, client.web_client)
    
    elif req.type == "interactive" and req.payload.get("type") == "block_actions":
        event = BlockActionEvent.parse(req.payload)
        print(event)
        # Here you would dispatch to an action handler
        # For example: action_dispatch(event, client.web_client)





if __name__ == "__main__":
    # Initialize SocketModeClient with an app-level token and a WebClient
    client = SocketModeClient(
        app_token=os.environ["SLACK_APP_LEVEL_TOKEN"],
        web_client=WebClient(token=os.environ["SLACK_BOT_OAUTH_TOKEN"])
    )
    # Add a listener for "events_api" events (like messages)
    client.socket_mode_request_listeners.append(process_message)
    
    # Establish a connection and start listening for events
    print("🤖 Bot is listening for messages...")
    client.connect()
    while True:
        try:
            tEvent().wait()
        except KeyboardInterrupt:
            break
        except Exception as e:
            logging.error(f"Uncaught exception:", exc_info=True)
            
