import os, logging, secrets
from threading import Event as tEvent
from datetime import datetime

from dotenv import load_dotenv
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.client import BaseSocketModeClient
from slack_sdk.web import WebClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

from schema.base import Event, Recv
from schema.message import MessageEvent
from schema.huddle import HuddleChange, HuddleState
from schema.interactive import BlockActionEvent
from reg import message_dispatch, msg_listen, action_dispatch, action_listen, huddle_dispatch, huddle_listen
from crypto.core import DeterRnd, Handler
import db
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

@msg_listen("live.init")
def init_game(event: MessageEvent, client: WebClient):
    """
    Starts a new game in the channel's active huddle.
    Only authorized users can trigger this command.
    """
    # A predefined list of users who are authorized to start games.
    # In a real application, this might come from the database or a config file.
    AUTHORIZED_USERS = ["U092BGL0UUQ"]

    user_id = event.message.user
    channel_id = event.channel

    if user_id not in AUTHORIZED_USERS:
        client.chat_postMessage(channel=user_id, text="You are not authorized to start a game.")
        return

    huddle_id = db.get_huddle_id_by_channel(channel_id)
    if not huddle_id:
        client.chat_postMessage(channel=channel_id, text="No active huddle found in this channel.")
        return

    if db.get_active_game_in_huddle(huddle_id):
        client.chat_postMessage(channel=channel_id, text="A game is already active in this huddle.")
        return

    client_secret = secrets.token_hex(16)
    server_secret = secrets.token_hex(16)
    game_id = db.start_game(huddle_id, datetime.utcnow(), client_secret, server_secret)
    
    client.chat_postMessage(channel=channel_id, text=f"✨ A new game has started! (ID: {game_id})")

@action_listen("test_button")
def handle_test_button(event: BlockActionEvent, client: WebClient):
    """Handles the click of the 'test_button'."""
    user_name = event.user.name
    client.chat_postMessage(
        channel=event.container.channel_id,
        text=f"👋 Hello {user_name}, you clicked the button!"
    )

@huddle_listen(HuddleState.IN_HUDDLE)
def handle_huddle_join(event: HuddleChange, client: WebClient):
    """Handles a user joining a huddle."""
    user_id = event.user.id
    user_name = event.user.name
    huddle_id = event.call_id
    db.upsert_user(user_id, user_name)
    db.add_huddle_participant(huddle_id, user_id)
    print(f"ℹ️ User {user_name} ({user_id}) joined huddle {huddle_id}.")

    game_id = db.get_active_game_in_huddle(huddle_id)
    if game_id is not None:
        db.add_game_participant(game_id, user_id)

@huddle_listen(HuddleState.NOT_IN_HUDDLE)
def handle_huddle_leave(event: HuddleChange, client: WebClient):
    """Handles a user leaving a huddle by removing them from the huddle participant list."""
    user_id = event.user.id
    user_name = event.user.name
    huddle_id = event.call_id
    db.remove_huddle_participant(huddle_id, user_id)
    print(f"🚪 User {user_name} ({user_id}) left huddle {huddle_id}.")

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
        event_payload = req.payload.get("event", {})
        event_type = event_payload.get("type")

        if event_type == "message" and "bot_id" not in event_payload:
            
            event = MessageEvent.parse(req.payload)
            print(event)
            message_dispatch(event, client.web_client)
        
        elif event_type == "user_huddle_changed":
            event = HuddleChange.parse(req.payload)
            print(event)
            huddle_dispatch(event, client.web_client)
    
    elif req.type == "interactive" and req.payload.get("type") == "block_actions":
        event = BlockActionEvent.parse(req.payload)
        print(event)
        action_dispatch(event, client.web_client)




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
            
