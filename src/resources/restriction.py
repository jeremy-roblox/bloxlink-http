import logging
from typing import Literal

import hikari
from attrs import define, field

from resources.api.roblox import users
from resources.bloxlink import UserData
from resources.bloxlink import instance as bloxlink
from resources.constants import RED_COLOR
from resources.exceptions import UserNotVerified
from resources.ui.embeds import InteractiveMessage
from resources.api.roblox.groups import RobloxGroup


@define
class Restriction:
    """Representation of how a restriction applies to a user, if at all."""

    restricted: bool = False
    reason: str | None = None
    action: str | None = Literal["kick", "ban", "dm", None]
    source: str | None = Literal["ageLimit", "groupLock", "disallowAlts", "banEvader", None]

    async def moderate(self, user_id: int, guild: hikari.Guild):
        """Kick or Ban a user based on the determined restriction.

        Args:
            user_id (int): ID of the user to moderate.
            guild (hikari.Guild): The guild that the user is verifying in.
        """

        # Only DM users if they're being removed; reason will show in main guild otherwise.
        if self.action in {"kick", "ban"}:
            await self.dm_member(user_id, guild)

        reason = (
            f"({self.source}): {self.reason[:450]}"  # pylint: disable=unsubscriptable-object
            if self.reason
            else f"User was removed because they matched this server's {self.source} settings."
        )
        if self.action == "kick":
            await bloxlink.rest.kick_user(guild.id, user_id, reason=reason)
        elif self.action == "ban":
            await bloxlink.rest.ban_user(guild.id, user_id, reason=reason)

    async def dm_member(self, user_id: int, guild: hikari.Guild):
        embed = hikari.Embed()
        embed.title = "User Restricted"

        reason_suffix = ""
        match self.source:
            # fmt:off
            case "ageLimit":
                reason_suffix = "this guild requires users to have a Roblox account older than a certain age"
            case "groupLock":
                reason_suffix = "this guild requires users to be in, or have a specific rank in, a Roblox group"
            case "banEvader":
                reason_suffix = "this guild does not allow ban evasion"
            # fmt:on

        embed.description = f"You were removed from **{guild.name}** because {reason_suffix}."

        if self.reason not in {"banEvader", "disallowAlts"}:
            embed.add_field(name="Reason", value=self.reason)

        try:
            # Only DM if the user is being kicked or banned. Reason is shown to user in guild otherwise.
            if self.action != "dm":
                channel = await bloxlink.rest.create_dm_channel(user_id)
                await channel.send(embed=embed)

        except (hikari.BadRequestError, hikari.ForbiddenError, hikari.NotFoundError) as e:
            logging.warning(e)


async def check_for_alts(guild_id: str, user_id: int, roblox_users: list) -> bool:
    matches = []
    for account in roblox_users:
        matches.extend(await bloxlink.reverse_lookup(account, user_id))

    alts_found: bool = False
    for user in matches:
        # sanity check, make sure we don't falsely match the user as themselves.
        if str(user_id) == user:
            continue

        member = await bloxlink.fetch_discord_member(guild_id, user, "id")

        if member is not None:
            # Always kick the matching alt users.
            try:
                await bloxlink.rest.kick_user(
                    guild_id, user, reason=f"User is an alt of {user_id} and disallowAlts is enabled."
                )
                alts_found = True

            except (hikari.NotFoundError, hikari.ForbiddenError):
                pass

    return alts_found


async def check_for_ban_evasion(guild_id: str, user_id: int, roblox_users: list) -> dict:
    matches = []
    for account in roblox_users:
        matches.extend(await bloxlink.reverse_lookup(account, user_id))

    response = {"match": False}

    for user in matches:
        if str(user_id) == user:
            continue

        try:
            await bloxlink.rest.fetch_ban(guild_id, user)
        except hikari.NotFoundError:
            continue
        except hikari.ForbiddenError:
            continue
        else:
            response["match_id"] = user
            response["match"] = True
            break

    return response
