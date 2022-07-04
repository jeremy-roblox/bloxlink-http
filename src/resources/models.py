from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any
import copy

__all__ = (
    "BloxlinkUser",
    "BloxlinkGuild",
    "PartialBloxlinkGuild",
    "PartialBloxlinkUser",
    "RobloxAccount",
)

def default_field(obj):
    return field(default_factory=lambda: copy.copy(obj))

class PartialMixin:

    __slots__ = ()

    def __getattr__(self, name: str) -> Any:
        with suppress(AttributeError):
            return super().__getattr__(name)

    def __getattribute__(self, __name: str) -> Any:
        with suppress(AttributeError):
            return super().__getattribute__(__name)


@dataclass(slots=True)
class BloxlinkUser(PartialMixin):
    id: int
    robloxID: str = None
    robloxAccounts: dict = default_field({"accounts":[], "guilds": {}})


@dataclass(slots=True)
class BloxlinkGuild:
    id: int
    binds: list = default_field([]) # FIXME


# @dataclass(slots=True)
# class PartialBloxlinkUser(BloxlinkUser, PartialMixin):
#     id: int
#     robloxID: str
#     robloxAccounts: list = field(default_factory=list)


# @dataclass(slots=True)
# class PartialBloxlinkGuild(BloxlinkGuild, PartialMixin):
#     pass

