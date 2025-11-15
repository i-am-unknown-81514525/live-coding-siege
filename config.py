import functools
from typing import TypedDict
import tomllib

class GroupConfig(TypedDict):
    allowed: list[str]
    authorized: list[str]
    namespace: list[str]
    module: str

type AllGroupConfig = dict[str, GroupConfig]

class Bot(TypedDict):
    group: AllGroupConfig

class Top(TypedDict):
    bot: Bot

@functools.cache
def get_config() -> Top:
    with open("config.toml", "rb") as f:
        return tomllib.load(f) # pyright: ignore[reportReturnType]