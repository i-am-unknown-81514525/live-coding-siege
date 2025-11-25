from dataclasses import dataclass
from slack_sdk.socket_mode.client import BaseSocketModeClient
from abc import ABC, abstractmethod
import threading

@dataclass
class ExecutionContext:
    slack_client: BaseSocketModeClient
    irc_client: object # tbd - the actual irc class

class Client[T](ABC):
    def __init__(self, inner: T):
        self._client: T = inner

    @abstractmethod
    def start(self):
        ...
    
    @property
    def client(self) -> T:
        return self._client

    def start_threaded(self) -> threading.Thread:
        thread = threading.Thread(target=self.start)
        thread.start()
        return thread
