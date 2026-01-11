import logging
import os
from importlib import import_module

from threading import Thread
from types import ModuleType

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from base import ExecutionContext

from irc.client import IRCClient
from irc.schema.event import Event
from slack.reg import (
    slash_listen,
    Context,
    smart_multi_msg_listen,
)
from irc.reg import irc_msg_listen
from base import (
    DESCRIPTION,
    description,
)

from slack.client import SlackClient

import utils

load_dotenv()

CLIENTS = [
    SlackClient(SocketModeClient(
        app_token=os.environ["SLACK_APP_LEVEL_TOKEN"],
        web_client=WebClient(token=os.environ["SLACK_BOT_OAUTH_TOKEN"]),
    )),
    IRCClient(
        server="irc.hackclub.com",
        port=6667,
        nickname="livecoding",
        realname="Live Coding Bot",
        boot_events=[
            Event.from_parts(cmd="JOIN", params=["#livecoding"]),
            Event.from_parts(cmd="JOIN", params=["#siege"])
        ],
    )
]
START_MODULE = ["live.server", "siege.core", "siege.remind", "live.live", "timer", "homelab.core"]
LOAD_MODULE = ["siege.cmd", "live.live", "homelab.cmd"]
HELP_CMD = ["live.help", "siege.help", "live.helps", "siege.helps"]
CONTEXT = ExecutionContext(
    slack_client=CLIENTS[0],
    irc_client=CLIENTS[1],
)

all_module: dict[str, ModuleType] = {}
client_thread: list[Thread] = []


@smart_multi_msg_listen(HELP_CMD)
@slash_listen("/help")
@irc_msg_listen("siege.help")
@description(
    "/help <prefix>?", "Help command to hopefully answer your random question?"
)
@utils.get_group
@utils.filter_allowed
@utils.have_any_group()
def help(ctx: Context, public: bool):
    items = []
    for cmd, description in DESCRIPTION.items():
        if cmd.startswith(ctx.value):
            items.append(f"`{cmd}` - {description}")
    message = (
        f"*Command list{f' with prefix "{ctx.value}"' if ctx.value else ''}*\n"
        + ("\n".join(items) or "No command exist with the given prefix")
    )
    if public:
        ctx.public_send(text=message)
    else:
        ctx.private_send(text=message)



if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for module_name in START_MODULE:
        try:
            module = import_module(module_name)
            all_module[module_name] = module
            module.start(CONTEXT)
        except Exception as e:
            logging.error(f"Failed to load start_module {module_name}:", exc_info=True)
    for module_name in LOAD_MODULE:
        try:
            module = import_module(module_name)
            all_module[module_name] = module
        except Exception as e:
            logging.error(f"Failed to load load_module {module_name}:", exc_info=True)
    for client in CLIENTS:
        client_thread.append(client.start_threaded())
    while True:
        try:
            for thread in client_thread:
                thread.join()
        except KeyboardInterrupt:
            break

