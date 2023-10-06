import copy
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Literal

import hikari

from resources.response import Response
from resources.roblox.roblox_entity import RobloxEntity, create_entity

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
    """Representation of a User's data in Bloxlink

    Attributes:
        id (int): The Discord ID of the user.
        robloxID (str): The roblox ID of the user's primary account.
        robloxAccounts (dict): All of the user's linked accounts, and any guild specific verifications.
    """

    id: int
    robloxID: str = None
    robloxAccounts: dict = default_field({"accounts": [], "guilds": {}})


@dataclass(slots=True)
class GuildData:
    """Representation of the stored settings for a guild"""

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
    """Data related to a command that has been run.

    Attributes:
        command_name (str): The name of the command triggered.
        command_id (int): The ID of the command triggered.
        guild_id (int): The name of the command triggered.
        member (hikari.InteractionMember): The member that triggered this command.
        user (hikari.User): The user that triggered this command.
        resolved (hikari.ResolvedOptionData): Data of entities mentioned in command arguments that are
            resolved by Discord.
        options (dict): The options/arguments passed by the user to this command.
        interaction (hikari.CommandInteraction): The interaction object from Discord.
        response (Response): Bloxlink's wrapper for handling initial response sending.
    """

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
    """UNUSED: Used to represent some missing datatype."""


@dataclass(slots=True)
class EmbedPrompt:
    """Represents a prompt consisting of an embed & components for the message."""

    embed: hikari.Embed = hikari.Embed()
    components: list = field(default_factory=list)


@dataclass(slots=True)
class GuildBind:
    """Represents a binding from the database.

    Post init it should be expected that the id, type, and entity types are not None.

    Attributes:
        nickname (str, optional): The nickname template to be applied to users. Defaults to None.
        roles (list): The IDs of roles that should be given by this bind.
        removeRole (list): The IDs of roles that should be removed when this bind is given.

        id (int, optional): The ID of the entity for this binding. Defaults to None.
        type (Literal[group, asset, gamepass, badge]): The type of binding this is representing.
        bind (dict): The raw data that the database stores for this binding.

        entity (RobloxEntity, optional): The entity that this binding represents. Defaults to None.
    """

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
    """Represents additional attributes that only apply to group binds.

    Except for min and max (which are used for ranges), only one attribute should be considered to be
    not None at a time.

    Attributes:
        min (int, optional): The minimum rank that this bind applies to. Defaults to None.
        max (int, optional): The maximum rank that this bind applies to. Defaults to None.
        roleset (int, optional): The specific rank that this bind applies to. Defaults to None.
            Can be negative (in legacy format) to signify that specific rank and higher.
        everyone (bool, optional): Does this bind apply to everyone. Defaults to None.
        guest (bool, optional): Does this bind apply to guests. Defaults to None.
    """

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
        """The specific type of this group bind.

        Returns:
            str: "linked_group" or "group_roles" depending on if there
                are roles explicitly listed to be given or not.
        """
        if not self.roles or self.roles in ("undefined", "null"):
            return "linked_group"
        else:
            return "group_roles"
