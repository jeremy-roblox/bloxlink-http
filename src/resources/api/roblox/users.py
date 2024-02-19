from __future__ import annotations

from datetime import timedelta

from bloxlink_lib import RobloxUser, get_user
from bloxlink_lib.database import fetch_guild_data, redis
import hikari

from resources.constants import VERIFY_URL, VERIFY_URL_GUILD
from resources.exceptions import RobloxAPIError, RobloxNotFound
from resources.premium import get_premium_status


async def get_user_from_string(target: str) -> RobloxUser:
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


async def format_embed(roblox_account: RobloxUser, user: hikari.User = None) -> hikari.Embed:
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
        embed.set_thumbnail(roblox_account.avatar_url)

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
        affiliate_enabled = ((await fetch_guild_data(guild_id, "affiliate")).affiliate or {}).get(
            "enabled"
        )

        # save where the user verified in
        # TODO: depreciated, remove
        await redis.set(f"verifying-from:{user_id}", guild_id, expire=timedelta(hours=1))

        if affiliate_enabled:
            await redis.set(f"affiliate-verifying-from:{user_id}", guild_id, expire=timedelta(hours=1))

        if affiliate_enabled or premium_status.active:
            return VERIFY_URL_GUILD.format(guild_id=guild_id)

    return VERIFY_URL
