import logging
import os
from importlib import import_module

from types import ModuleType

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.client import BaseSocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

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
    smart_multi_msg_listen,
)

import utils
from schema.base import Recv
from schema.huddle import HuddleChange
from schema.interactive import BlockActionEvent
from schema.message import MessageEvent
from schema.slash_cmd import CommandEvent

load_dotenv()

CLIENTS = []
START_MODULE = ["live.server", "siege.core", "siege.remind", "live.live"]
LOAD_MODULE = ["siege.cmd", "live.live"]
HELP_CMD = ["live.help", "siege.help", "live.helps", "siege.helps"]


all_module: dict[str, ModuleType] = {}


@smart_multi_msg_listen(HELP_CMD)
@slash_listen("/help")
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
    
