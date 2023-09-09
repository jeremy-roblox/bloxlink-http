import copy
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Literal

import hikari

from resources.roblox.roblox_entity import RobloxEntity, create_entity

from .response import Response

__all__ = (
    "CommandContext",
    "EmbedPrompt",
    "GroupBind",
    "GuildBind",
    "GuildData",
    "MISSING",
    "PremiumModel",
    "UserData",
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


@dataclass(slots=True)
class EmbedPrompt:
    embed: hikari.Embed = hikari.Embed()
    components: list = field(default_factory=list)


@dataclass(slots=True)
class GuildBind:
    nickname: str = None
    roles: list = default_field(list())
    removeRoles: list = default_field(list())

    id: int = None
    type: Literal["group", "asset", "gamepass", "badge"] = Literal["group", "asset", "gamepass", "badge"]
    bind: dict = default_field({"type": "", "id": None})

    entity: RobloxEntity = None

    def __post_init__(self):
        self.id = self.bind.get("id")
        self.type = self.bind.get("type")

        self.entity = create_entity(self.type, self.id)


class GroupBind(GuildBind):
    min: int = None
    max: int = None
    roleset: int = None
    everyone: bool = None
    guest: bool = None

    def __post_init__(self):
        self.min = self.bind.get("min", None)
        self.max = self.bind.get("max", None)
        self.roleset = self.bind.get("roleset", None)
        self.everyone = self.bind.get("everyone", None)
        self.guest = self.bind.get("guest", None)

        return super().__post_init__()

    @property
    def subtype(self) -> str:
        """Returns the type of group bind that this is.

        Returns:
            str: Either "linked_group" or "group_roles" depending on if there
                are roles explicitly listed to be given or not.
        """
        if not self.roles or self.roles in ("undefined", "null"):
            return "linked_group"
        else:
            return "group_roles"
