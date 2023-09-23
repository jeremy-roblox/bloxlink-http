from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

import dateutil.parser as parser
import hikari

import resources.binds as binds
import resources.roblox.groups as groups
from resources.bloxlink import instance as bloxlink
from resources.constants import ALL_USER_API_SCOPES
from resources.exceptions import UserNotVerified
from resources.models import PartialMixin, UserData
from resources.utils import ReturnType, fetch


@dataclass(slots=True)
class RobloxAccount(PartialMixin):
    id: str
    username: str = None
    banned: bool = None
    age_days: int = None
    groups: dict = None
    avatar: str = None
    description: str = None
    profile_link: str = None
    display_name: str = None
    created: str = None
    badges: list = None
    short_age_string: str = None
    flags: int = None
    overlay: int = None

    complete: bool = False

    _data: dict = field(default_factory=lambda: {})

    async def sync(self, includes=None, *, cache=True, no_flag_check=False):
        if includes is None:
            includes = []
        elif includes is True:
            includes = ALL_USER_API_SCOPES
            self.complete = True

        if cache:
            # remove includes if we already have the value saved
            if self.groups is not None and "groups" in includes:
                includes.remove("groups")

            if self.presence is not None and "presence" in includes:
                includes.remove("presence")

            if self.badges is not None and "badges" in includes:
                includes.remove("badges")

        includes = ",".join(includes)

        id_string = "id" if not self.id else f"id={self.id}"
        username_string = "username" if not self.username else f"username={self.username}"

        user_json_data, user_data_response = await fetch(
            "GET",
            f"https://bloxlink-info-server-vunlj.ondigitalocean.app/roblox/info?{id_string}&{username_string}&include={includes}",
            return_data=ReturnType.JSON,
        )

        if user_data_response.status == 200:
            self.description = user_json_data.get("description", self.description)
            self.username = user_json_data.get("name", self.name)
            self.banned = user_json_data.get("isBanned", self.banned)
            self.profile_link = user_json_data.get("profileLink", self.profile_link)
            self.badges = user_json_data.get("badges", self.badges)
            self.display_name = user_json_data.get("displayName", self.display_name)
            self.created = user_json_data.get("created", self.created)

            self._data.update(user_json_data)

            await self.parse_groups(user_json_data.get("groups"))

            if self.badges and self.groups and not no_flag_check:
                await self.parse_flags()

            self.parse_age()

            avatar = user_json_data.get("avatar")

            if avatar:
                avatar_url, avatar_response = await fetch("GET", avatar["bustThumbnail"])

                if avatar_response.status == 200:
                    self.avatar = avatar_url.get("data", [{}])[0].get("imageUrl")

    async def get_group_ranks(self, guild) -> dict:
        group_ranks = {}

        if self.groups is None:
            await self.sync(includes=["groups"])

        linked_groups = await binds.get_linked_group_ids(guild)

        for group_id in linked_groups:
            group = self.groups.get(group_id)

            if group:
                group_ranks[group.name] = group.rank_name

        return group_ranks

    def parse_age(self):
        if (self.age_days is not None) or not self.created:
            return

        today = datetime.today()
        roblox_user_age = parser.parse(self.created).replace(tzinfo=None)
        self.age_days = (today - roblox_user_age).days

        self._data.update({"age_days": self.age_days})

        if not self.short_age_string:
            if self.age_days >= 365:
                years = math.floor(self.age_days / 365)
                ending = f"yr{((years > 1 or years == 0) and 's') or ''}"
                self.short_age_string = f"{years} {ending} ago"
            else:
                ending = f"day{((self.age_days > 1 or self.age_days == 0) and 's') or ''}"
                self.short_age_string = f"{self.age_days} {ending} ago"

    async def parse_flags(self):
        if self.flags is not None:
            return

        if self.badges is None or self.groups is None:
            await self.sync(includes=["badges", "groups"], cache=True, no_flag_check=True)

        if self.groups is None:
            print("error for flags", self.name, self.id)
            return

        flags = 0

        # if "3587262" in self.groups and self.groups["3587262"].rank_value >= 50:
        #     flags = flags | BLOXLINK_STAFF

        # if "4199740" in self.groups:
        #     flags = flags | RBX_STAR

        # if self.badges and "Administrator" in self.badges:
        #     flags = flags | RBX_STAFF

        # self.flags = flags
        # self.overlay = self.flags & RBX_STAFF or self.flags & RBX_STAFF or self.flags & RBX_STAR

    async def parse_groups(self, group_json: dict | None):
        if group_json is None:
            return

        self.groups = {}

        for group_data in group_json:
            group_meta = group_data.get("group")
            group_role = group_data.get("role")

            group: groups.RobloxGroup = groups.RobloxGroup(
                id=str(group_meta["id"]),
                name=group_meta["name"],
                user_roleset=group_role,
            )  # seems redundant, but this is so we can switch the endpoint and retain consistency
            await group.sync()
            self.groups[group.id] = group

    def to_dict(self):
        return self._data


async def get_user_account(
    user: hikari.User | str, guild_id: int = None, raise_errors=True
) -> RobloxAccount | None:
    """get a user's linked Roblox account"""

    user_id = str(user.id) if isinstance(user, hikari.User) else str(user)
    bloxlink_user: UserData = await bloxlink.fetch_user_data(user_id, "robloxID", "robloxAccounts")

    if guild_id:
        guild_account = (bloxlink_user.robloxAccounts or {}).get(str(guild_id))

        if guild_account:
            return RobloxAccount(id=guild_account)

    if bloxlink_user.robloxID:
        return RobloxAccount(id=bloxlink_user.robloxID)

    if raise_errors:
        raise UserNotVerified()
    else:
        return None


async def get_user(
    user: hikari.User = None,
    includes: list = None,
    *,
    roblox_username: str = None,
    roblox_id: int = None,
    guild_id: int = None,
) -> RobloxAccount:
    """get a Roblox account"""

    roblox_account: RobloxAccount = None

    if user:
        roblox_account = await get_user_account(user, guild_id)
        await roblox_account.sync(includes)

    else:
        roblox_account = RobloxAccount(username=roblox_username, id=roblox_id)
        await roblox_account.sync(includes)

    return roblox_account


async def format_embed(roblox_account: RobloxAccount, user: hikari.User = None) -> hikari.Embed:
    await roblox_account.sync()

    embed = hikari.Embed(
        title=str(user) if user else roblox_account.display_name,
        url=roblox_account.profile_link,
    )

    embed.add_field(name="Username", value=f"@{roblox_account.username}", inline=True)
    embed.add_field(name="ID", value=roblox_account.id, inline=True)
    embed.add_field(
        name="Description",
        value=roblox_account.description[:500] if roblox_account.description else "None provided",
        inline=False,
    )

    embed.set_thumbnail(roblox_account.avatar)

    return embed
