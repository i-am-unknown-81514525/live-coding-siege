import socket
from typing import Self

from base import Client
from irc.schema.event import Event


class IRCClient(Client["IRCClient"]):
    def __init__(self, server: str, port: int, nickname: str, realname: str):
        self.server = server
        self.port = port
        self.nickname = nickname
        self.realname = realname
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        super().__init__(self)
    
    def start(self):
        self.sock.connect((self.server, self.port))
        bootstrap = [
            Event.from_parts(cmd="NICK", params=[self.nickname]),
            Event.from_parts(cmd="USER", params=[self.nickname, "0", "*"], trailing=self.realname),
        ]
        for event in bootstrap:
            self.sock.send(event.export(with_prefix=True).encode("utf-8"))
        
        while True:
            data = self.sock.recv(4096)
            if not data:
                break
            lines = data.decode("utf-8").split("\r\n")
            for line in lines:
                if line:
                    event = Event.import_event(line + "\r\n")
                    if event:
                        self.handler(event)

    
    def handler(self, event: Event):
        if event.cmd == "PING":
            pong = Event.from_parts(cmd="PONG", trailing=event.trailing)
            self.sock.send(pong.export().encode("utf-8"))
            return
        ...
        