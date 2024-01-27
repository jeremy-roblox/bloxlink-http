from __future__ import annotations

import math
from datetime import datetime
from datetime import timedelta
from attrs import define, field

from dateutil import parser
import hikari
from attrs import define, field

import resources.api.roblox.groups as groups
from resources.bloxlink import instance as bloxlink
from resources.constants import ALL_USER_API_SCOPES, VERIFY_URL, VERIFY_URL_GUILD
from resources.exceptions import RobloxAPIError, RobloxNotFound, UserNotVerified
from resources.fetch import fetch
from resources.premium import get_premium_status
from resources.redis import redis
from config import CONFIG


@define(slots=True)
class RobloxAccount: # pylint: disable=too-many-instance-attributes
    """Representation of a user on Roblox."""

    id: str = field(converter=str)
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

    _data: dict = field(factory=lambda: {})

    async def sync(
        self,
        includes: list | bool | None = None,
        *,
        cache: bool = True,
    ):
        """Retrieve information about this user from Roblox. Requires a username or id to be set.

        Args:
            includes (list | bool | None, optional): Data that should be included. Defaults to None.
                True retrieves all available data. Otherwise a list can be passed with either
                "groups", "presences", and/or "badges" in it.
            cache (bool, optional): Should we check the object for values before retrieving. Defaults to True.
            flag_check (bool, optional): . Defaults to False.
        """
        if includes is None:
            includes = []
        elif includes is True:
            includes = ALL_USER_API_SCOPES
            self.complete = True

        if cache:
            # remove includes if we already have the value saved
            if self.groups is not None and "groups" in includes:
                includes.remove("groups")

            if self.badges is not None and "badges" in includes:
                includes.remove("badges")

        includes = ",".join(includes)

        id_string = "id" if not self.id else f"id={self.id}"
        username_string = "username" if not self.username else f"username={self.username}"

        user_json_data, user_data_response = await fetch(
            "GET",
            f"{CONFIG.ROBLOX_INFO_SERVER}/roblox/info?{id_string}&{username_string}&include={includes}",
            parse_as="JSON",
        )

        if user_data_response.status == 200:
            self.id = user_json_data.get("id", self.id)
            self.description = user_json_data.get("description", self.description)
            self.username = user_json_data.get("name", self.username)
            self.banned = user_json_data.get("isBanned", self.banned)
            self.profile_link = user_json_data.get("profileLink", self.profile_link)
            self.badges = user_json_data.get("badges", self.badges)
            self.display_name = user_json_data.get("displayName", self.display_name)
            self.created = user_json_data.get("created", self.created)

            self._data.update(user_json_data)

            await self.parse_groups(user_json_data.get("groups"))

            self.parse_age()

            avatar = user_json_data.get("avatar")

            if avatar:
                avatar_url, avatar_response = await fetch("GET", avatar["bustThumbnail"])

                if avatar_response.status == 200:
                    self.avatar = avatar_url.get("data", [{}])[0].get("imageUrl")

    def parse_age(self):
        """Set a human-readable string representing how old this account is."""
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

    async def parse_groups(self, group_json: dict | None):
        """Determine what groups this user is in from a json response.

        Args:
            group_json (dict | None): JSON input from Roblox representing a user's groups.
        """
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
        """Return a dictionary representing this roblox account"""
        return self._data


async def get_user_account(
    user: hikari.User | str, guild_id: int = None, raise_errors=True
) -> RobloxAccount | None:
    """Get a user's linked Roblox account.

    Args:
        user (hikari.User | str): The User or user ID to find the linked Roblox account for.
        guild_id (int, optional): Used to determine what account is linked in the given guild id.
            Defaults to None.
        raise_errors (bool, optional): Should errors be raised or not. Defaults to True.

    Raises:
        UserNotVerified: If raise_errors and user is not linked with Bloxlink.

    Returns:
        RobloxAccount | None: The linked Roblox account either globally or for this guild, if any.
    """

    user_id = str(user.id) if isinstance(user, hikari.User) else str(user)
    bloxlink_user = await bloxlink.fetch_user_data(user_id, "robloxID", "robloxAccounts")

    if guild_id:
        guild_accounts = (bloxlink_user.robloxAccounts or {}).get("guilds") or {}

        guild_account = guild_accounts.get(str(guild_id))

        if guild_account:
            return RobloxAccount(id=guild_account)

    if bloxlink_user.robloxID:
        return RobloxAccount(id=bloxlink_user.robloxID)

    if raise_errors:
        raise UserNotVerified()

    return None

async def get_user(
    user: hikari.User = None,
    includes: list = None,
    *,
    roblox_username: str = None,
    roblox_id: int = None,
    guild_id: int = None,
) -> RobloxAccount:
    """Get a Roblox account.

    If a user is not passed, it is required that either roblox_username OR roblox_id is given.

    roblox_id takes priority over roblox_username when searching for users.

    guild_id only applies when a user is given.

    Args:
        user (hikari.User, optional): Get the account linked to this user. Defaults to None.
        includes (list | bool | None, optional): Data that should be included. Defaults to None.
            True retrieves all available data. Otherwise a list can be passed with either
            "groups", "presences", and/or "badges" in it.
        roblox_username (str, optional): Username of the account to get. Defaults to None.
        roblox_id (int, optional): ID of the account to get. Defaults to None.
        guild_id (int, optional): Guild ID if looking up a user to determine the linked account in that guild.
            Defaults to None.

    Returns:
        RobloxAccount | None: The found Roblox account, if any.
    """

    roblox_account: RobloxAccount = None

    if user:
        roblox_account = await get_user_account(user, guild_id)
        await roblox_account.sync(includes)

    else:
        roblox_account = RobloxAccount(username=roblox_username, id=roblox_id)
        await roblox_account.sync(includes)

    return roblox_account


async def get_accounts(user: hikari.User) -> list[RobloxAccount]:
    """Get a user's linked Roblox accounts.

    Args:
        user (hikari.User): The user to get linked accounts for.

    Returns:
        list[RobloxAccount]: The linked Roblox accounts for this user.
    """

    user_id = str(user.id)
    bloxlink_user = await bloxlink.fetch_user_data(user_id, "robloxID", "robloxAccounts")

    account_ids = set()

    if bloxlink_user.robloxID:
        account_ids.add(bloxlink_user.robloxID)

    guild_accounts = (bloxlink_user.robloxAccounts or {}).get("guilds") or {}

    for guild_account_id in guild_accounts.values():
        account_ids.add(guild_account_id)

    accounts = [
        RobloxAccount(id=account_id) for account_id in account_ids
    ]

    return accounts


async def reverse_lookup(roblox_account: RobloxAccount, exclude_user_id: int | None = None) -> list[str]:
    """Find Discord IDs linked to a roblox id.

    Args:
        roblox_account (RobloxAccount): The roblox account that will be matched against.
        exclude_user_id (int | None, optional): Discord user ID that will not be included in the output.
            Defaults to None.

    Returns:
        list[str]: All the discord IDs linked to this roblox_id.
    """
    cursor = bloxlink.mongo.bloxlink["users"].find(
        {"$or": [{"robloxID": roblox_account.id}, {"robloxAccounts.accounts": roblox_account.id}]},
        {"_id": 1},
    )

    return [x["_id"] async for x in cursor if str(exclude_user_id) != str(x["_id"])]

async def get_user_from_string(target: str) -> RobloxAccount:
    """Get a RobloxAccount from a given target string (either an ID or username)

    Args:
        target (str): Roblox ID or username of the account to sync.

    Raises:
        RobloxNotFound: When no user is found.
        *Other exceptions may be raised such as RobloxAPIError from get_user*

    Returns:
        RobloxAccount: The synced RobloxAccount of the user requested.
    """
    account = None

    if target.isdigit():
        try:
            account = await get_user(roblox_id=target)
        except (RobloxNotFound, RobloxAPIError):
            pass

    # Fallback to parse input as a username if the input was not a valid id.
    if account is None:
        try:
            account = await get_user(roblox_username=target)
        except RobloxNotFound as exc:
            raise RobloxNotFound(
                "The Roblox user you were searching for does not exist! "
                "Please check the input you gave and try again!"
            ) from exc

    if account.id is None or account.username is None:
        raise RobloxNotFound("The Roblox user you were searching for does not exist.")

    return account


async def format_embed(roblox_account: RobloxAccount, user: hikari.User = None) -> hikari.Embed:
    """Create an embed displaying information about a user.

    Args:
        roblox_account (RobloxAccount): The user to display information for. Should be synced.
        user (hikari.User, optional): Discord user for this roblox account. Defaults to None.

    Returns:
        hikari.Embed: Embed with information about a roblox account.
    """
    await roblox_account.sync()

    embed = hikari.Embed(
        title=str(user) if user else roblox_account.display_name,
        url=roblox_account.profile_link,
    )

    embed.add_field(name="Username", value=f"@{roblox_account.username}", inline=True)
    embed.add_field(name="ID", value=str(roblox_account.id), inline=True)
    embed.add_field(
        name="Description",
        value=roblox_account.description[:500] if roblox_account.description else "None provided",
        inline=False,
    )

    if roblox_account.avatar:
        embed.set_thumbnail(roblox_account.avatar)

    return embed


async def get_verification_link(
    user_id: int | str, guild_id: int | str = None, interaction: hikari.ComponentInteraction = None
) -> str:
    """Get the verification link for a user.

    Args:
        user_id (int | str): The user to get the verification link for.
        guild_id (int | str, optional): The guild ID to get the verification link for. Defaults to None.
        interaction (hikari.ComponentInteraction, optional): The interaction to check for premium status. Defaults to None.

    Returns:
        str: The verification link for the user.
    """

    if guild_id:
        guild_id = str(guild_id)

        premium_status = await get_premium_status(guild_id=guild_id, interaction=interaction)
        affiliate_enabled = ((await bloxlink.fetch_guild_data(guild_id, "affiliate")).affiliate or {}).get(
            "enabled"
        )

        # save where the user verified in
        # TODO: depreciated, remove
        await redis.set(f"verifying-from:{user_id}", guild_id, ex=timedelta(hours=1).seconds)

        if affiliate_enabled:
            await redis.set(f"affiliate-verifying-from:{user_id}", guild_id, ex=timedelta(hours=1).seconds)

        if affiliate_enabled or premium_status.active:
            return VERIFY_URL_GUILD.format(guild_id=guild_id)

    return VERIFY_URL
