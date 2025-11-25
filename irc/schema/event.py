from dataclasses import dataclass
from frozenlist import FrozenList
from typing import Self
import re

_FROZEN = FrozenList()
_FROZEN.freeze()

@dataclass
class Event:
    cmd: str
    prefix: str | None = None # this would exclude the ':'
    params: FrozenList[str] = _FROZEN
    trailing: str | None = None

    @classmethod
    def import_event(cls, content: str) -> Self | None:
        match = re.fullmatch(r"^(?::([^ \r\n:]+) )?([^ \r\n:]+) ((?:[^ \r\n:]+ +)*)(:([^\r\n]*))?\r\n$", content)
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
    
    def export(self, with_prefix: bool = False) -> str:
        ret: str = ""
        if with_prefix and self.prefix is not None:
            ret += f":{self.prefix} "
        ret += f"{self.cmd} "
        ret += " ".join(self.params) + " "
        if self.trailing is not None:
            ret += f":{self.trailing}"
        ret += "\r\n"
        return ret

    @classmethod
    def from_parts(
        cls,
        cmd: str,
        *,
        prefix: str | None = None,
        params: list[str] | None = None,
        trailing: str | None = None
    ) -> Self:
        frozen_params = _FROZEN
        if params is not None:
            frozen_params = FrozenList(params)
            frozen_params.freeze()
        return cls(
            cmd=cmd,
            prefix=prefix,
            params=frozen_params,
            trailing=trailing
        )