import socket
from typing import Self

from base import Client
from irc.schema.event import Event
import logging
import time


class IRCClient(Client["IRCClient"]):
    def __init__(self, server: str, port: int, nickname: str, realname: str, boot_events: list[Event] | None = None):
        self.server = server
        self.port = port
        self.nickname = nickname
        self.realname = realname
        self.boot_events = boot_events or []
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ran_boot = False
        super().__init__(self)
    
    def start(self):
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as self.sock:
                try:
                    self.ran_boot = False
                    self.sock.connect((self.server, self.port))
                    bootstrap = [
                        Event.from_parts(cmd="NICK", params=[self.nickname]),
                        Event.from_parts(cmd="USER", params=["guest", "0", "*"], trailing=self.realname),
                    ]
                    for event in bootstrap:
                        self.send(event)

                    while True:
                        data = self.sock.recv(4096)
                        logging.info(f"IRC RAW <-: {data.decode('utf-8')}".replace("\r", "\\r").replace("\n", "\\n"))
                        if not data:
                            break
                        lines = data.decode("utf-8").split("\r\n")
                        for line in lines:
                            if line:
                                event = Event.import_event(line + "\r\n")
                                if event:
                                    self.handler(event)
                except Exception as e:
                    logging.warning("IRC connection failed", exc_info=True)
                    time.sleep(10)

    
    def handler(self, event: Event):
        logging.info(f"IRC <-: {event.export(with_prefix=True).strip()}")
        if event.cmd == "PING":
            pong = Event.from_parts(cmd="PONG", trailing=event.trailing)
            self.send(pong)
            return
        if event.cmd == "001" and not self.ran_boot:
            self.ran_boot = True
            for boot_event in self.boot_events:
                self.send(boot_event)
            return
        
    def send(self, event: Event):
        logging.info(f"IRC ->: {event.export(with_prefix=True).strip()}")
        self.sock.send(event.export(with_prefix=True).encode("utf-8"))