from .models import UserData, PartialMixin
from snowfin import User
from .bloxlink import instance as bloxlink
from .exceptions import UserNotVerified
import resources.binds as binds
import resources.groups as groups
from .constants import ALL_USER_API_SCOPES
from datetime import datetime
import math
from .utils import fetch, ReturnType
import dateutil.parser as parser
from dataclasses import dataclass


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

        user_json_data, user_data_response = await fetch(f"https://bloxlink-info-server-vunlj.ondigitalocean.app/roblox/info?id={self.id}&include={includes}", return_data=ReturnType.JSON)

        if user_data_response.status == 200:
            self.description = user_json_data.get("description", self.description)
            self.username = user_json_data.get("name", self.name)
            self.banned = user_json_data.get("isBanned", self.banned)
            self.profile_link = user_json_data.get("profileLink", self.profile_link)
            self.badges = user_json_data.get("badges", self.badges)
            self.display_name = user_json_data.get("displayName", self.display_name)
            self.created = user_json_data.get("created", self.created)

            await self.parse_groups(user_json_data.get("groups"))

            if self.badges and self.groups and not no_flag_check:
                await self.parse_flags()

            self.parse_age()

            avatar = user_json_data.get("avatar")

            if avatar:
                avatar_url, avatar_response = await fetch(avatar["bustThumbnail"])

                if avatar_response.status == 200:
                    self.avatar = avatar_url.get("data", [{}])[0].get("imageUrl")

    async def get_group_ranks(self, guild):
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

        if not self.short_age_string:
            if self.age_days >= 365:
                years = math.floor(self.age_days/365)
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

    async def parse_groups(self, group_json):
        if group_json is None:
            return

        self.groups = {}

        for group_data in group_json:
            group_meta = group_data.get("group")
            group_role = group_data.get("role")

            group: groups.RobloxGroup = groups.RobloxGroup(id=str(group_meta["id"]),
                                                           name=group_meta["name"],
                                                           my_role={"name": group_role["name"].strip(), "rank": group_role["rank"]}) # seems redundant, but this is so we can switch the endpoint and retain consistency
            await group.sync()
            self.groups[group.id] = group




async def get_user_account(user: User, guild_id: int = None, raise_errors=True) -> RobloxAccount | None:
    """get a user's linked Roblox account"""

    bloxlink_user: UserData = await bloxlink.fetch_user(str(user.user.id), "robloxID", "robloxAccounts")

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


async def get_user(user: User = None, includes: list = None, *, roblox_username: str = None, roblox_id: int = None, guild_id: int = None) -> RobloxAccount:
    """get a Roblox account"""

    roblox_account: RobloxAccount = None

    if user:
        roblox_account = await get_user_account(user, guild_id)
        await roblox_account.sync(includes)

    else:
        roblox_account = RobloxAccount(username=roblox_username, id=roblox_id)
        await roblox_account.sync(includes)

    return roblox_account
