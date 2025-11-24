from dataclasses import dataclass
from slack_sdk.socket_mode.client import BaseSocketModeClient

@dataclass
class ExecutionContext:
    slack_client: BaseSocketModeClient
    irc_client: object # tbd - the actual irc class

