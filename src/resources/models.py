from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any
import copy
import hikari
from .response import Response


__all__ = ("UserData", "GuildData", "RobloxAccount", "CommandContext", "BaseGuildBind", "PremiumModel", "MISSING")


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
class UserData(PartialMixin):
    id: int
    robloxID: str = None
    robloxAccounts: dict = default_field({"accounts": [], "guilds": {}})


@dataclass(slots=True)
class GuildData:
    id: int
    binds: list = default_field([])  # FIXME

    verifiedRoleEnabled: bool = True
    verifiedRoleName: str = "Verified"  # deprecated
    verifiedRole: str = None

    unverifiedRoleEnabled: bool = True
    unverifiedRoleName: str = "Unverified"  # deprecated
    unverifiedRole: str = None

    premium: dict = None


@dataclass(slots=True)
class CommandContext:
    command_name: str
    command_id: int
    guild_id: int
    member: hikari.InteractionMember
    user: hikari.User
    resolved: hikari.ResolvedOptionData
    options: dict[str, str | int]

    response: Response

@dataclass(slots=True)
class PremiumModel:
    active: bool = False
    type: str = None
    payment_source: str = None
    tier: str = None
    term: str = None
    features: set = None

    def __str__(self):
        buffer = []

        if self.features:
            if "premium" in self.features:
                buffer.append("Basic - Premium commands")
            if "pro" in self.features:
                buffer.append("Pro - Unlocks the Pro bot and a few [enterprise features](https://blox.link/pricing)")

        return "\n".join(buffer) or "Not premium"


@dataclass(slots=True)
class BaseGuildBind:
    nickname: str = None
    roles: list = None
    removeRoles: list = None

    id: int = None
    type: str = ""  # Expected type strings: group, asset, gamepass, badge
    bind: dict = default_field({"type": "", "id": None})

    min: int = None
    max: int = None
    roleset: int = None
    everyone: bool = None
    guest: bool = None

    def __post_init__(self):
        self.id = self.bind.get("id")
        self.type = self.bind.get("type")

        self.min = self.bind.get("min", None)
        self.max = self.bind.get("max", None)
        self.roleset = self.bind.get("roleset", None)
        self.everyone = self.bind.get("everyone", None)
        self.guest = self.bind.get("guest", None)



class MISSING:
    pass
