from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

import hikari

import resources.roblox.users as users
from resources.constants import (
    GROUP_RANK_CRITERIA_TEXT,
    RED_COLOR,
    REPLY_CONT,
    REPLY_EMOTE,
)
from resources.exceptions import (
    BloxlinkException,
    BloxlinkForbidden,
    Message,
    RobloxAPIError,
    RobloxNotFound,
    UserNotVerified,
)
from resources.roblox.groups import RobloxGroup
from resources.roblox.roblox_entity import RobloxEntity, create_entity
from resources.secrets import BOT_API, BOT_API_AUTH

from .bloxlink import instance as bloxlink
from .models import GuildData, UserData, default_field
from .utils import fetch

nickname_template_regex = re.compile(r"\{(.*?)\}")
any_group_nickname = re.compile(r"\{group-rank-(.*?)\}")
bracket_search = re.compile(r"\[(.*)\]")


async def count_binds(guild_id: int | str, group_id: int | str = None) -> int:
    guild_data: GuildData = await bloxlink.fetch_guild_data(str(guild_id), "binds")

    return (
        len(guild_data.binds)
        if not group_id
        else sum(1 for b in guild_data.binds if b["bind"]["id"] == int(group_id)) or 0
    )


async def get_bind_desc(
    guild_id: int | str,
    bind_id: int | str = None,
    bind_type: Literal["group", "asset", "badge", "gamepass"] = None,
):
    guild_binds = (await bloxlink.fetch_guild_data(guild_id, "binds")).binds
    guild_binds = json_binds_to_guild_binds(guild_binds, category=bind_type, id_filter=bind_id)

    bind_strings = [await bind_description_generator(bind) for bind in guild_binds]

    output = "\n".join(bind_strings[:5])
    if len(bind_strings) > 5:
        output += (
            f"\n_... and {len(bind_strings) - 5} more. "
            f"Click [here](https://www.blox.link/dashboard/guilds/{guild_id}/binds) to view the rest!_"
        )
    return output


async def create_bind(
    guild_id: int | str,
    bind_type: Literal["group", "asset", "badge", "gamepass"],
    bind_id: int,
    roles: list[str] = None,
    remove_roles: list[str] = None,
    nickname: str = None,
    **bind_data,
):
    """creates a new guild bind. if it already exists, the roles will be appended"""

    guild_binds: list = (await bloxlink.fetch_guild_data(str(guild_id), "binds")).binds

    existing_binds = []
    for bind in guild_binds:
        b = bind["bind"]

        if b["type"] != bind_type:
            continue
        if b.get("id") != bind_id:
            continue

        if len(bind_data) > 0:
            cond = (
                (b.get("roleset") == bind_data.get("roleset") if "roleset" in bind_data else False)
                or (b.get("min") == bind_data.get("min") if "min" in bind_data else False)
                or (b.get("max") == bind_data.get("max") if "max" in bind_data else False)
                or (b.get("guest") == bind_data.get("guest") if "guest" in bind_data else False)
                or (b.get("everyone") == bind_data.get("everyone") if "everyone" in bind_data else False)
            )
            if not cond:
                continue
        elif len(b) > 2 and len(bind_data) == 0:
            continue

        existing_binds.append(bind)

    if not existing_binds:
        new_bind = {
            "roles": roles,
            "removeRoles": remove_roles,
            "nickname": nickname,
            "bind": {"type": bind_type, "id": bind_id, **bind_data},
        }

        guild_binds.append(new_bind)

        await bloxlink.update_guild_data(guild_id, binds=guild_binds)

        return

    if bind_id:
        # group, badge, gamepass, and asset binds
        if len(existing_binds) > 1:
            # invalid bind. binds with IDs should only have one entry.
            raise NotImplementedError(
                "Binds with IDs should only have one entry. More than one duplicate was found."
            )
        else:
            if roles:
                # Remove invalid guild roles
                guild_roles = set((await bloxlink.fetch_roles(guild_id)).keys())
                existing_roles = set(existing_binds[0].get("roles", []) + roles)

                # Moves binding to the end of the array, if we wanted order to stay could get the
                # index, then remove, then insert again at that index.
                guild_binds.remove(existing_binds[0])

                existing_binds[0]["roles"] = list(guild_roles & existing_roles)
                guild_binds.append(existing_binds[0])
            else:
                # In ideal circumstances, this case should be for entire group bindings only
                raise NotImplementedError("No roles to be assigned were passed.")

            if remove_roles:
                # Override roles to remove rather than append.
                guild_binds.remove(existing_binds[0])

                existing_binds[0]["removeRoles"] = remove_roles
                guild_binds.append(existing_binds[0])

            await bloxlink.update_guild_data(guild_id, binds=guild_binds)

    else:
        # everything else
        raise NotImplementedError("No bind_id was passed when trying to make a bind.")


async def delete_bind(
    guild_id: int | str,
    bind_type: Literal["group", "asset", "badge", "gamepass"],
    bind_id: int,
    **bind_data,
):
    subquery = {
        "binds": {
            "bind": {
                "type": bind_type,
                "id": int(bind_id),
                **bind_data,
            }
        }
    }

    await bloxlink.mongo.bloxlink["guilds"].update_one({"_id": str(guild_id)}, {"$pull": subquery})


async def apply_binds(
    member: hikari.Member | dict,
    guild_id: hikari.Snowflake,
    roblox_account: users.RobloxAccount = None,
    *,
    moderate_user=False,
) -> hikari.Embed:
    """Apply bindings to a user, (apply the Verified & Unverified roles, nickname template, and custom bindings).

    Args:
        member (hikari.Member | dict): Information of the member being updated.
            For dicts, the valid keys are as follows:
            "role_ids", "id", "username" (or "name"), "nickname", "avatar_url"
        guild_id (hikari.Snowflake): The ID of the guild where the user is being updated.
        roblox_account (users.RobloxAccount, optional): The linked account of the user if one exists. May
            or may not be their primary account, could be a guild-specific link. Defaults to None.
        moderate_user (bool, optional): Check if any restrictions (age limit, group lock,
            ban evasion, alt detection) apply to this user. Defaults to False.

    Raises:
        Message: Raised if there was an issue getting a server's bindings.
        RuntimeError: Raised if the nickname endpoint on the bot API encountered an issue.
        BloxlinkForbidden: Raised when Bloxlink does not have permissions to give roles to a user.

    Returns:
        hikari.Embed: The embed that will be shown to the user.
    """
    if roblox_account and roblox_account.groups is None:
        await roblox_account.sync(["groups"])

    guild: hikari.RESTGuild = await bloxlink.rest.fetch_guild(guild_id)

    role_ids = []
    member_id = None
    username = ""
    nickname = ""
    avatar_url = ""
    user_tag = ""

    # Get necessary user information.
    if isinstance(member, hikari.Member):
        role_ids = member.role_ids
        member_id = member.id
        username = member.username
        nickname = member.nickname
        avatar_url = member.display_avatar_url.url
        user_tag = f"{username}#{member.discriminator}"

    elif isinstance(member, dict):
        role_ids = member.get("role_ids", [])
        member_id = member.get("id")
        username = member.get("username", None)

        if not username:
            username = member.get("name", "")

        nickname = member.get("nickname", "")
        avatar_url = member.get("avatar_url", "")
        user_tag = f"{username}#{member.get('discriminator')}"

    member_roles: dict = {}
    for member_role_id in role_ids:
        if role := guild.roles.get(member_role_id):
            member_roles[role.id] = {
                "id": role.id,
                "name": role.name,
                "managed": bool(role.bot_id) and role.name != "@everyone",
            }

    # add_roles:    set = set() # used exclusively for display purposes
    add_roles: list[hikari.Role] = []
    remove_roles: list[hikari.Role] = []
    possible_nicknames: list[list[hikari.Role | str]] = []
    warnings: list[str] = []
    chosen_nickname = None
    applied_nickname = None

    # Handle restrictions.
    restrict_result = None
    if moderate_user:
        restrict_result = await _check_guild_restrictions(
            guild_id,
            {
                "id": member_id,
                "roles": member_roles,
                "account": roblox_account,
            },
        )

    if restrict_result is not None:
        await restrict_result.moderate(member_id, guild)

        if restrict_result.removed:
            return restrict_result.prompt(guild.name)

        if restrict_result.restriction == "disallowAlts":
            warnings.append(
                "This server does not allow alt accounts, because of this your other accounts have "
                "been kicked from this server."
            )

    restricted_flag = False if (restrict_result is None or restrict_result.restriction == "disallowAlts") else True

    # TODO: Add restricted flag so that way only the unverified role is given if a user is restricted.
    # Get user's bindings (includes verified + unverified roles) to apply + nickname templates.
    user_binds, user_binds_response = await fetch(
        "POST",
        f"{BOT_API}/binds/{member_id}",
        headers={"Authorization": BOT_API_AUTH},
        body={
            "guild": {
                "id": guild.id,
                "roles": [
                    {"id": r.id, "name": r.name, "managed": bool(r.bot_id) and r.name != "@everyone"}
                    for r in guild.roles.values()
                ],
            },
            "member": {"id": member_id, "roles": member_roles},
            "roblox_account": roblox_account.to_dict() if roblox_account else None,
            "restricted": restricted_flag
        },
    )

    if user_binds_response.status == 200:
        user_binds = user_binds["binds"]
    else:
        raise Message("Something went wrong getting this user's relevant bindings!")

    # first apply the required binds, then ask the user if they want to apply the optional binds

    for required_bind in user_binds["required"]:
        # find valid roles from the server

        for bind_add_id in required_bind[1]:
            if role := guild.roles.get(int(bind_add_id)):
                add_roles.append(role)

                if required_bind[3]:
                    possible_nicknames.append([role, required_bind[3]])

        for bind_remove_id in required_bind[2]:
            if role := guild.roles.get(bind_remove_id):
                remove_roles.append(role)

    # real_add_roles = add_roles

    # remove_roles   = remove_roles.difference(add_roles) # added roles get priority
    # real_add_roles = add_roles.difference(set(member.roles)) # remove roles that are already on the user, also new variable so we can achieve idempotence

    # if real_add_roles or remove_roles:
    #     await bloxlink.edit_user_roles(member, guild_id, add_roles=real_add_roles, remove_roles=remove_roles)

    if possible_nicknames:
        if len(possible_nicknames) == 1:
            chosen_nickname = possible_nicknames[0][1]
        else:
            # get highest role with a nickname
            highest_role = sorted(possible_nicknames, key=lambda e: e[0].position, reverse=True)

            if highest_role:
                chosen_nickname = highest_role[0][1]

        if chosen_nickname:
            chosen_nickname_http, nickname_response = await fetch(
                "GET",
                f"{BOT_API}/nickname/parse/",
                headers={"Authorization": BOT_API_AUTH},
                body={
                    "user_data": {"name": username, "nick": nickname, "id": member_id},
                    "guild_id": guild.id,
                    "guild_name": guild.name,
                    "roblox_account": roblox_account.to_dict() if roblox_account else None,
                    "template": chosen_nickname,
                    "restricted": restricted_flag,
                },
            )

            if nickname_response.status == 200:
                chosen_nickname = chosen_nickname_http["nickname"]
            else:
                raise RuntimeError(f"Nickname API returned an error: {chosen_nickname_http}")

            if str(guild.owner_id) == str(member_id):
                warnings.append(
                    f"Since you're the Server Owner, I cannot modify your nickname.\nNickname: {chosen_nickname}"
                )
            else:
                try:
                    await bloxlink.rest.edit_member(guild_id, member_id, nickname=chosen_nickname)

                except hikari.errors.ForbiddenError:
                    warnings.append("I don't have permission to change the nickname of this user.")

                else:
                    applied_nickname = chosen_nickname

    try:
        if add_roles or remove_roles:
            # since this overwrites their roles, we need to add in their current roles
            # then, we remove the remove_roles from the set
            await bloxlink.rest.edit_member(
                guild_id,
                member_id,
                roles=set(getattr(r, "id", r) for r in add_roles + role_ids).difference(
                    [r.id for r in remove_roles]
                ),
            )
    except hikari.errors.ForbiddenError:
        raise BloxlinkForbidden("I don't have permission to add roles to this user.")

    if restrict_result is not None and not restrict_result.removed:
        return restrict_result.prompt(guild.name)

    if add_roles or remove_roles or warnings:
        embed = hikari.Embed(
            title="Member Updated",
        )
        embed.set_author(
            name=user_tag,
            icon=avatar_url,
            url=roblox_account.profile_link if roblox_account else None,
        )

        if add_roles:
            embed.add_field(name="Added Roles", value=",".join([r.mention for r in add_roles]))

        if remove_roles:
            embed.add_field(name="Removed Roles", value=",".join([r.mention for r in remove_roles]))

        if applied_nickname:
            embed.add_field(name="Nickname Changed", value=applied_nickname)

        if warnings:
            embed.add_field(name=f"Warning{'s' if len(warnings) >= 2 else ''}", value="\n".join(warnings))

    else:
        embed = hikari.Embed(description="No binds apply to you!")

    return embed


@dataclass
class Restriction:
    removed: bool = False
    action: str | None = Literal["kick", "ban", "dm", None]
    restriction: str | None = Literal["ageLimit", "groupLock", "disallowAlts", "banEvader", None]
    metadata: dict = default_field({"unverified": True})

    def prompt(self, guild_name: str) -> hikari.Embed:
        """Return an Embed describing why the user was restricted.

        This prompt will be either DM'd to users or sent in replacement of the typical
        verification success message.
        The only time it is not sent for a restriction is for the disallowAlts restriction, where instead
        a reason will be appended to the success embed as a warning.

        Args:
            guild_name (str): Name of the guild that the user was trying to verify in.

        Returns:
            hikari.Embed: User-facing embed.
        """
        embed = hikari.Embed()

        embed.set_author(name=f"You could not be verified in {guild_name.capitalize()}!")

        unverified: bool = self.metadata["unverified"]
        description = "You are not verified with Bloxlink!"

        try:
            if unverified:
                raise UserNotVerified()

            match self.restriction:
                case "ageLimit":
                    age_limit_data = self.metadata["ageLimit"]
                    description = (
                        "Your linked Roblox account is not old enough to verify in this server!\n"
                        f"Your account needs to be {age_limit_data[0]} days old, "
                        f"and is only {age_limit_data[1]} days old."
                    )

                case "groupLock":
                    group: RobloxGroup = self.metadata["group"]
                    roleset_restriction = self.metadata["roleset"]
                    dm_message = self.metadata["dmMessage"]

                    if roleset_restriction:
                        description = (
                            "You are not the required rank in "
                            f"[{group.name}](https://www.roblox.com/groups/{group.id})!"
                        )
                    else:
                        description = (
                            "This server requires that you join "
                            f"[{group.name}](https://www.roblox.com/groups/{group.id}) "
                            "before you can verify!"
                        )

                    if dm_message:
                        description += f"\nMessage from the server admins:\n>>> *{dm_message}*"

                case "disallowAlts":
                    # unused?
                    description = (
                        "This server allows you be verified to one Discord account at a time."
                        "Because of this your other accounts linked to your Roblox account have been kicked"
                        "from this server."
                    )

                case "banEvader":
                    description = "You have been removed because you are evading a ban in this server."

        except UserNotVerified:
            pass

        embed.color = RED_COLOR
        embed.description = description

        return embed

    async def moderate(self, user_id: int, guild: hikari.Guild):
        """DM, Kick, or Ban a user based on the determined restriction.

        Args:
            user_id (int): ID of the user to moderate.
            guild (hikari.Guild): The guild that the user is verifying in.
        """
        if self.removed or self.action is None or self.restriction is None:
            return

        prompt = self.prompt(guild.name)
        try:
            # Only DM if the user is being kicked or banned.
            if self.action != "dm":
                channel = await bloxlink.rest.create_dm_channel(user_id)
                await channel.send(embed=prompt)

        except (hikari.BadRequestError, hikari.ForbiddenError, hikari.NotFoundError) as e:
            logging.warning(e)

        try:
            log_reason = self._log_reason()
            if self.action == "kick":
                await bloxlink.rest.kick_user(guild.id, user_id, reason=log_reason)
            elif self.action == "ban":
                await bloxlink.rest.ban_user(guild.id, user_id, reason=log_reason)

        except (hikari.ForbiddenError, hikari.NotFoundError):
            pass
        else:
            if self.action != "dm":
                self.removed = True

    def _log_reason(self) -> str:
        """Generate a string for the audit log entry when a user is kicked or banned.

        Returns:
            str: The resulting audit log string.
        """
        response: str = f"RESTRICTED: {self.restriction}, "

        unverified: bool = self.metadata["unverified"]
        description = "Not verified with Bloxlink."

        try:
            if unverified:
                raise UserNotVerified()

            match self.restriction:
                case "ageLimit":
                    age_limit_data = self.metadata["ageLimit"]
                    description = (
                        "User's Roblox account does not meet the agelimit. "
                        f"{age_limit_data[1]} < {age_limit_data[0]} days."
                    )

                case "groupLock":
                    group: RobloxGroup = self.metadata["group"]
                    roleset_restriction = self.metadata["roleset"]

                    if roleset_restriction:
                        description = f"User is not the required rank in the group {str(group)}"
                    else:
                        description = f"User is not in the group {str(group)}"

                case "banEvader":
                    banned_id = self.metadata["banned_user"]
                    description = f"User is an alt of the banned account {banned_id}"

                case _:
                    description = "User matched a restriction."
        except UserNotVerified:
            pass

        return response + description


async def _check_guild_restrictions(guild_id: hikari.Snowflake, user_info: dict) -> Restriction | None:
    """Check if a user should be kept from verifying in this guild_id.

    Args:
        guild_id (hikari.Snowflake): ID of the guild that the user is verifying in.
        user_info (dict): Information of the user
            Expected to have "id": the user id, and "account" which is a RobloxAccount.

    Returns:
        Restriction | None: Restriction info if the user should be restricted.
    """
    guild_data = await bloxlink.fetch_guild_data(
        guild_id,
        "ageLimit",
        "disallowAlts",
        "disallowBanEvaders",
        "groupLock",
    )

    user_id = user_info["id"]
    user_acc: users.RobloxAccount = user_info["account"]

    # TODO: If server has premium and user_acc
    if user_acc:
        bloxlink_user: UserData = await bloxlink.fetch_user_data(user_id, "robloxID", "robloxAccounts")

        accounts = bloxlink_user.robloxAccounts["accounts"]
        accounts.append(bloxlink_user.robloxID)
        accounts = list(set(accounts))

        result = await _check_premium_restrictions(
            guild_data.disallowAlts,
            guild_data.disallowBanEvaders,
            user_id,
            guild_id,
            accounts,
        )

        if result:
            return result

    if guild_data.ageLimit:
        if not user_acc:
            return Restriction(action="kick", restriction="ageLimit", metadata={"unverified": True})

        if user_acc.age_days < guild_data.ageLimit:
            return Restriction(
                action="kick",
                restriction="ageLimit",
                metadata={"unverified": False, "ageLimit": (guild_data.ageLimit, user_acc.age_days)},
            )

    if guild_data.groupLock:
        if not user_acc:
            kick_unverified = any(
                g.get("unverifiedAction", "kick") == "kick" for g in guild_data.groupLock.values()
            )

            return Restriction(
                action="kick" if kick_unverified else "dm",
                restriction="groupLock",
                metadata={"unverified": True},
            )

        if user_acc.groups is None:
            await user_acc.sync(includes=["groups"])

        for group_id, group_data in guild_data.groupLock.items():
            action = group_data.get("verifiedAction", "dm")
            required_rolesets = group_data.get("roleSets")

            dm_message = group_data.get("dmMessage")

            group_match: RobloxGroup = user_acc.groups.get(group_id)
            group = group_match if group_match is not None else RobloxGroup(group_id)
            await group.sync()

            if group_match is None:
                return Restriction(
                    action=action,
                    restriction="groupLock",
                    metadata={"unverified": False, "group": group, "dmMessage": dm_message, "roleset": False},
                )

            user_roleset = group_match.user_roleset["rank"]
            for roleset in required_rolesets:
                if isinstance(roleset, list):
                    # within range
                    if roleset[0] <= user_roleset <= roleset[1]:
                        break
                else:
                    # exact match (x) or inverse match (rolesets above x)
                    if (user_roleset == roleset) or (roleset < 0 and abs(roleset) <= user_roleset):
                        break
            else:
                # no match was found - restrict the user.
                return Restriction(
                    action=action,
                    restriction="groupLock",
                    metadata={"unverified": False, "group": group, "dmMessage": dm_message, "roleset": True},
                )


async def _check_premium_restrictions(
    check_alts: bool,
    check_ban_evaders: str | None,
    user_id: int,
    guild_id: int,
    user_accounts: list,
) -> Restriction | None:
    """Check for alts and ban evaders within a server for a user.

    Args:
        check_alts (bool): Should we check for alts
        check_ban_evaders (str | None): Should we check for ban evaders
        user_id (int): Discord ID of the user being updated
        guild_id (int): Guild ID where the user is being updated
        user_accounts (list): Roblox accounts linked to this user_id

    Returns:
        Restriction | None: Restriction info if the user is ban evading or an alt account
            was found.
    """
    if not check_alts and (not check_ban_evaders or check_ban_evaders is None):
        return

    matches = []
    for account in user_accounts:
        matches.extend(await bloxlink.reverse_lookup(account, user_id))

    alts_found: bool = False
    for user in matches:
        # sanity check, shouldn't be included but just in case.
        if str(user_id) == user:
            continue

        if check_alts:
            member = await bloxlink.fetch_discord_member(guild_id, user, "id")

            if member is not None:
                # We kick the old user here because otherwise the restriction will remove the original
                # user based on the code setup.

                try:
                    await bloxlink.rest.kick_user(
                        guild_id, user, reason=f"User is an alt of {user_id} and disallowAlts is enabled."
                    )

                    alts_found = True

                except (hikari.NotFoundError, hikari.ForbiddenError):
                    pass

                # We don't return so we can continue checking for more alts if they exist & kick them too.
                # Plus, returning will prevent ban evader checking.

        if check_ban_evaders:
            try:
                await bloxlink.rest.fetch_ban(guild_id, user)
            except hikari.NotFoundError:
                continue
            except hikari.ForbiddenError:
                continue
            else:
                return Restriction(
                    action="ban",
                    restriction="banEvader",
                    metadata={"unverified": False, "banned_user": user},
                )

        if alts_found:
            return Restriction(
                action="dm",
                restriction="disallowAlts",
                metadata={"unverified": False},
            )


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


def json_binds_to_guild_binds(bind_list: list, category: str = None, id_filter: str = None):
    binds = []

    if id_filter:
        id_filter = (
            None if id_filter.lower() == "none" or id_filter.lower() == "view binds" else str(id_filter)
        )

    for bind in bind_list:
        bind_data = bind.get("bind")
        bind_type = bind_data.get("type")

        if category and bind_type != category:
            continue

        if id_filter and str(bind_data.get("id")) != id_filter:
            continue

        if bind_type == "group":
            classed_bind = GroupBind(**bind)
        elif bind_type:
            classed_bind = GuildBind(**bind)
        else:
            raise BloxlinkException("Invalid bind structure found.")

        binds.append(classed_bind)

    bind_list = list(binds)
    if id_filter is not None:
        bind_list.sort(key=lambda e: e.id)
    return bind_list


def join_bind_strings(strings: list) -> str:
    """Helper method to use when joining all the strings for the viewbind embed.

    Uses emojis to display the strings in a tier-format where the top level is the "identifier" that the
    lower bind strings display as a subset of.

    Args:
        strings (list): List of string to join

    Returns:
        str: Tiered formatted string.
    """

    # Use REPLY_CONT for all but last element
    split_strings = [f"\n{REPLY_CONT}".join(strings[:-1]), strings[-1]] if len(strings) > 2 else strings
    return f"\n{REPLY_EMOTE}".join(split_strings)


async def bind_description_generator(bind: GroupBind | GuildBind) -> str:
    """Builds a sentence-formatted string for a binding.

    Results in the layout of: <USERS> <CONTENT ID/RANK> receive the role(s) <ROLE LIST>, and have the roles
    removed <REMOVE ROLE LIST>

    The remove role list is only appended if it there are roles to remove.

    Example output:
        All users in this group receive the role matching their group rank name.
        People with the rank Developers (200) receive the role @a
        People with a rank greater than or equal to Supporter (1) receive the role @b

    Args:
        bind (GroupBind | GuildBind): The binding to build the string for.

    Returns:
        str: The sentence description of this binding.
    """
    if isinstance(bind, GroupBind):
        if bind.subtype == "linked_group":
            return "- _All users in **this** group receive the role matching their group rank name._"

    if not bind.entity.synced:
        try:
            await bind.entity.sync()
        except RobloxNotFound:
            pass
        except RobloxAPIError:
            pass

    roles = bind.roles if bind.roles else []
    role_str = ", ".join(f"<@&{val}>" for val in roles)
    remove_roles = bind.removeRoles if bind.removeRoles else []
    remove_role_str = ", ".join(f"<@&{val}>" for val in remove_roles)

    prefix = _bind_desc_prefix_gen(bind)
    content = _bind_desc_content_gen(bind)

    return (
        f"- _{prefix} {f'**{content}**' if content else ''} receive the "
        f"role{'s' if len(roles) > 1  else ''} {role_str}"
        f"{'' if len(remove_roles) == 0 else f', and have these roles removed: {remove_role_str}'}_"
    )


def _bind_desc_prefix_gen(bind: GroupBind | GuildBind) -> str | None:
    """Generate the prefix string for a bind's description.

    Args:
        bind (GroupBind | GuildBind): Bind to generate the prefix for.

    Returns:
        str | None: The prefix if one should be set.
    """
    if not isinstance(bind, GroupBind):
        return f"People who own the {bind.type}"

    prefix = None
    if bind.min and bind.max:
        prefix = GROUP_RANK_CRITERIA_TEXT.get("rng")

    elif bind.min:
        prefix = GROUP_RANK_CRITERIA_TEXT.get("gte")

    elif bind.max:
        prefix = GROUP_RANK_CRITERIA_TEXT.get("lte")

    elif bind.roleset:
        if bind.roleset < 0:
            prefix = GROUP_RANK_CRITERIA_TEXT.get("gte")
        else:
            prefix = GROUP_RANK_CRITERIA_TEXT.get("equ")

    elif bind.guest:
        prefix = GROUP_RANK_CRITERIA_TEXT.get("gst")

    elif bind.everyone:
        prefix = GROUP_RANK_CRITERIA_TEXT.get("all")

    return prefix


def _bind_desc_content_gen(bind: GroupBind | GuildData) -> str | None:
    """Generate the content string for a bind's description.

    This will be the content that describes the rolesets to be given,
    or the name of the other entity that the bind is for.

    Args:
        bind (GroupBind | GuildBind): Bind to generate the content for.

    Returns:
        str | None: The content if it should be set.
            Roleset bindings like guest and everyone do not have content to display,
            as the given prefix string contains the content.
    """
    if not isinstance(bind, GroupBind):
        return str(bind.entity).replace("**", "")

    group = bind.entity
    content = None

    if bind.min and bind.max:
        min_str = group.roleset_name_string(bind.min, bold_name=False)
        max_str = group.roleset_name_string(bind.max, bold_name=False)
        content = f"{min_str}** and **{max_str}"

    elif bind.min:
        content = group.roleset_name_string(bind.min, bold_name=False)

    elif bind.max:
        content = group.roleset_name_string(bind.max, bold_name=False)

    elif bind.roleset:
        content = group.roleset_name_string(abs(bind.roleset), bold_name=False)

    return content
