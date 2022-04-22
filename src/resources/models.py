from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

__all__ = (
    "BloxlinkUser",
    "BloxlinkGuild",
    "PartialBloxlinkGuild",
    "PartialBloxlinkUser",
    "RobloxAccount",
)

class PartialMixin:

    __slots__ = ()

    def __getattr__(self, name: str) -> Any:
        with suppress(AttributeError):
            return super().__getattr__(name)

    def __getattribute__(self, __name: str) -> Any:
        with suppress(AttributeError):
            return super().__getattribute__(__name)


@dataclass(slots=True)
class BloxlinkUser:
    id: int


@dataclass(slots=True)
class BloxlinkGuild:
    id: int


@dataclass(slots=True)
class PartialBloxlinkUser(BloxlinkUser, PartialMixin):
    pass
    

@dataclass(slots=True)
class PartialBloxlinkGuild(BloxlinkGuild, PartialMixin):
    pass


@dataclass(slots=True)
class RobloxAccount:
    id: int
    username: str