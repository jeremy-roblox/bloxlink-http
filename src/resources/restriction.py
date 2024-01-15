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
        """DM, Kick, or Ban a user based on the determined restriction.

        Args:
            user_id (int): ID of the user to moderate.
            guild (hikari.Guild): The guild that the user is verifying in.
        """

        # TODO: Enable ability to DM users prior to their removal again.
        # prompt = self.prompt(guild.name)
        # try:
        #     # Only DM if the user is being kicked or banned.
        #     if self.action != "dm":
        #         channel = await bloxlink.rest.create_dm_channel(user_id)
        #         await channel.send(embed=prompt.embed)

        # except (hikari.BadRequestError, hikari.ForbiddenError, hikari.NotFoundError) as e:
        #     logging.warning(e)

        reason = (
            f"({self.source}): {self.reason[:450]}"  # pylint: disable=unsubscriptable-object
            if self.reason
            else f"User was removed because they matched this server's {self.source} settings."
        )
        if self.action == "kick":
            await bloxlink.rest.kick_user(guild.id, user_id, reason=reason)
        elif self.action == "ban":
            await bloxlink.rest.ban_user(guild.id, user_id, reason=reason)


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
