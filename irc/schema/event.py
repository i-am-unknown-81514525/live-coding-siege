from dataclasses import dataclass
from frozenlist import FrozenList
from typing import Self
import re

@dataclass
class Event:
    prefix: str | None # this would exclude the ':'
    cmd: str
    params: FrozenList[str]
    trailing: str | None = None

    @classmethod
    def import_event(cls, content: str) -> Self | None:
        match = re.fullmatch(r"^(?::([^ \r\n:]+) )? ([^ \r\n:]+) ((?:[^ \r\n:]+ +)*)(:([^\r\n]*))?\r\n$", content)
        if not match:
            return None
        prefix = match.group(1)
        cmd = match.group(2)
        params = FrozenList()
        if match.group(5) is not None:
            params = FrozenList(match.group(3).strip().split())
        params.freeze()
        trailing = None
        if match.group(4) is not None:
            if match.group(5) is not None:
                trailing = match.group(5)
            else:
                trailing = ""
        
        return cls(
            prefix=prefix,
            cmd=cmd,
            params=params,
            trailing=trailing
        )