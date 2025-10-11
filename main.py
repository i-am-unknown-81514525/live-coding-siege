import os, logging
from threading import Event

from dotenv import load_dotenv
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.client import BaseSocketModeClient
from slack_sdk.web import WebClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

load_dotenv()

# This function is called when a message is sent to a channel the bot is in
def process_message(client: BaseSocketModeClient, req: SocketModeRequest):
    # Acknowledge the event first
    response = SocketModeResponse(envelope_id=req.envelope_id)
    client.send_socket_mode_response(response)
    print(req.type, req.payload)
    with open("event.log", "a") as f:
        f.write(f"{req.type} {str(req.payload)}\n")
    
    # Check if the event is a message and not from a bot
    if req.type == "events_api" and req.payload["event"]["type"] == "message" and "bot_id" not in req.payload["event"]:
        
        # Extract message details
        message_text = req.payload["event"]["text"]
        channel_id = req.payload["event"]["channel"]
        user_id = req.payload["event"]["user"]
        
        # The specific string to listen for
        trigger_string = "hello bot"

        if trigger_string in message_text.lower():
            # Respond to the message in the same channel
            response_text = f"Hello <@{user_id}>! I'm here to help."
            client.web_client.chat_postMessage(. # type: ignore
                channel=channel_id,
                text=response_text
            )

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
            Event().wait()
        except KeyboardInterrupt:
            break
        except Exception as e:
            logging.error(f"Uncaught exception:", exc_info=True)
            
