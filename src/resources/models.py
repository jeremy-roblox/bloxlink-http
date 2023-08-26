import copy
from abc import ABC
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

import hikari

from .response import Response

__all__ = (
    "UserData",
    "GuildData",
    "RobloxAccount",
    "CommandContext",
    "PremiumModel",
    "MISSING",
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

    ageLimit: int = None
    disallowAlts: bool = None
    disallowBanEvaders: str = None  # Site sets it to "ban" when enabled. Null when disabled.
    groupLock: dict = None

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

    interaction: hikari.CommandInteraction

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
                buffer.append(
                    "Pro - Unlocks the Pro bot and a few [enterprise features](https://blox.link/pricing)"
                )

        return "\n".join(buffer) or "Not premium"


class MISSING:
    pass
