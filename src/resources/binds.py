from __future__ import annotations
from .models import BaseGuildBind, GuildData, MISSING
import resources.users as users
import resources.groups as groups
import resources.assets as assets
import resources.badges as badges
import resources.gamepasses as gamepasses
from resources.exceptions import BloxlinkException, BloxlinkForbidden, Message, RobloxNotFound
from resources.constants import DEFAULTS, REPLY_CONT, REPLY_EMOTE, GROUP_RANK_CRITERIA_TEXT
from resources.secrets import BOT_API, BOT_API_AUTH
from .bloxlink import instance as bloxlink
from .utils import fetch
from typing import Literal
import hikari
import re


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
    bind_strings = []

    guild_binds = (await bloxlink.fetch_guild_data(guild_id, "binds")).binds

    for bind in guild_binds:
        bind_gb = GuildBind(**bind)

        if bind_id and str(bind_gb.id) != str(bind_id):
            continue

        if bind_type and bind_gb.type != bind_type:
            continue

        bind_strings.append(await bind_gb.get_bind_string(viewbind_styling=False))

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


async def apply_binds(
    member: hikari.Member | dict,
    guild_id: hikari.Snowflake,
    roblox_account: users.RobloxAccount = None,
    *,
    moderate_user=False,
) -> hikari.Embed:
    if roblox_account and roblox_account.groups is None:
        await roblox_account.sync(["groups"])

    guild: hikari.RESTGuild = await bloxlink.rest.fetch_guild(guild_id)

    role_ids = []
    member_id = None
    username = ""
    nickname = ""
    avatar_url = ""
    user_tag = ""

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
        },
    )

    if user_binds_response.status == 200:
        user_binds = user_binds["binds"]
    else:
        raise Message("Something went wrong getting this user's relevant bindings!")

    # first apply the required binds, then ask the user if they want to apply the optional binds

    # add_roles:    set = set() # used exclusively for display purposes
    add_roles: list[hikari.Role] = []
    remove_roles: list[hikari.Role] = []
    possible_nicknames: list[list[hikari.Role | str]] = []
    warnings: list[str] = []
    chosen_nickname = None
    applied_nickname = None

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


def json_binds_to_guild_binds(bind_list: list, category: str = None, id_filter: str = None):
    binds = []

    if id_filter:
        id_filter = None if id_filter.lower() == "none" or id_filter.lower() == "view binds" else id_filter

    for bind in bind_list:
        classed_bind = GuildBind(**bind)

        if category and classed_bind.type != category:
            continue

        if id_filter and str(classed_bind.id) != id_filter:
            continue

        binds.append(classed_bind)

    return list(binds)


class GuildBind(BaseGuildBind):
    def determine_type(self) -> str:
        """Returns what specific type of binds this is. In particular it distinguishes between
        a linked group binding (linked_group return) and a bound role id (group_roles return).
        All other types return as they are named (asset, badge, gamepass)"""

        if self.type == "group":
            if not self.roles or self.roles in ("undefined", "null"):
                return "linked_group"
            else:
                return "group_roles"
        else:
            return self.type

    async def get_bind_string(
        self,
        include_id: bool = True,
        include_name: bool = True,
        viewbind_styling: bool = True,
    ) -> str:
        """Returns a string representing the bind, formatted in the way /viewbinds expects it.

        Args:
            include_id (bool): For viewbind styling, include the ID in the output.
            include_name (bool): For viewbind styling, include the name of the entity in the output.
            viewbind_styling (bool): Determine if the output should visually match what the viewbind prompt
                shows, or if it should appear as the text-based output used in the bind prompt.

        Returns:
            String representation of this binding.
        """

        if viewbind_styling:
            # role_string = await bloxlink.role_ids_to_names(guild_id=guild_id, roles=self.roles)
            role_string = ", ".join([f"<@&{role}>" for role in self.roles]) if self.roles else ""
            remove_role_str = ""

            if self.removeRoles and (self.removeRoles != "null" or self.removeRoles != "undefined"):
                remove_role_str = "Remove Roles:" + ", ".join([f"<@&{role}>" for role in self.removeRoles])
                # remove_role_str = (
                #     f"Remove Roles: {await bloxlink.role_ids_to_names(guild_id=guild_id, roles=self.removeRoles)}"
                # )

            name_id_string = await named_string_builder(self.type, self.id, include_id, include_name)

            nickname_string = f"Nickname: `{self.nickname}`" if self.nickname else ""
            role_string = f"Role(s): {role_string}"

            output_list = []

            if self.type == "group":
                # Entire group binding.
                if not self.roles or self.roles == "undefined" or self.roles == "null":
                    output_list = [name_id_string]
                    if nickname_string:
                        output_list.append(nickname_string)
                    if remove_role_str:
                        output_list.append(remove_role_str)

                else:
                    # Every other group binding type (range, guest, everyone, single ID)
                    rank_string = ""

                    rolesets = dict()
                    try:
                        group = await groups.get_group(self.id)
                        rolesets = group.rolesets
                    except RobloxNotFound:
                        # We can pass here since for the rest of the data, the default for no
                        # item will be to insert the id by itself, rather than including the name
                        pass

                    if self.min is not None and self.max is not None:
                        min_name = rolesets.get(self.min, "")
                        max_name = rolesets.get(self.max, "")

                        min_str = f"**{min_name}** ({self.min})" if min_name else f"{self.min}"
                        max_str = f"**{max_name}** ({self.max})" if max_name else f"{self.max}"
                        rank_string = f"Ranks {min_str} to {max_str}:"

                    elif self.min is not None:
                        min_name = rolesets.get(self.min, "")
                        min_str = f"**{min_name}** ({self.min})" if min_name else f"{self.min}"
                        rank_string = f"Rank {min_str} or above:"

                    elif self.max is not None:
                        max_name = rolesets.get(self.max, "")
                        max_str = f"**{max_name}** ({self.max})" if max_name else f"{self.max}"
                        rank_string = f"Rank {max_str} or below:"
                        pass

                    elif self.roleset is not None:
                        abs_roleset = abs(self.roleset)
                        roleset_name = rolesets.get(abs_roleset, "")
                        roleset_str = (
                            f"**{roleset_name}** ({abs_roleset})" if roleset_name else f"{abs_roleset}"
                        )

                        if self.roleset <= 0:
                            rank_string = f"Rank {roleset_str} or above:"
                        else:
                            rank_string = f"Rank {roleset_str}:"

                    elif self.everyone:
                        rank_string = "**All group members:**"

                    elif self.guest:
                        rank_string = "**Non-group members:**"

                    # Append only accepts one value at a time, so do this.
                    if name_id_string:
                        output_list.append(name_id_string)
                    output_list.append(rank_string)
                    output_list.append(role_string)
                    if nickname_string:
                        output_list.append(nickname_string)
                    if remove_role_str:
                        output_list.append(remove_role_str)
            else:
                output_list = list(
                    filter(None, [name_id_string, nickname_string, role_string, remove_role_str])
                )

            return join_bind_strings(output_list)
        else:
            roles = self.roles if self.roles else []
            role_str = ", ".join(f"<@&{val}>" for val in roles)
            remove_roles = self.removeRoles if self.removeRoles else []
            remove_role_str = ", ".join(f"<@&{val}>" for val in remove_roles)

            bind_type = self.type

            prefix = ""
            content = ""

            if bind_type == "group":
                subtype = self.determine_type()
                if subtype == "linked_group":
                    return f"- _All users in this group ({self.id}) receive the role matching their group rank name._"

                elif subtype == "group_roles":
                    if self.min and self.max:
                        # TODO: Consider grabbing rank names.
                        prefix = GROUP_RANK_CRITERIA_TEXT.get("rng")
                        content = f"{self.min}** and **{self.max}"

                    elif self.min:
                        prefix = GROUP_RANK_CRITERIA_TEXT.get("gte")
                        content = self.min

                    elif self.max:
                        prefix = GROUP_RANK_CRITERIA_TEXT.get("lte")
                        content = self.max

                    elif self.roleset:
                        if self.roleset < 0:
                            prefix = GROUP_RANK_CRITERIA_TEXT.get("gte")
                            content = abs(self.roleset)
                        else:
                            prefix = GROUP_RANK_CRITERIA_TEXT.get("equ")
                            content = self.roleset

                    elif self.guest:
                        prefix = GROUP_RANK_CRITERIA_TEXT.get("gst")

                    elif self.everyone:
                        prefix = GROUP_RANK_CRITERIA_TEXT.get("all")

            elif bind_type == "asset":
                prefix = "People who own the asset"
                content = await named_string_builder(bind_type, self.id, include_name=True, include_id=False)
            elif bind_type == "badge":
                prefix = "People who own the badge"
                content = await named_string_builder(bind_type, self.id, include_name=True, include_id=False)
            elif bind_type == "gamepass":
                prefix = "People who own the gamepass"
                content = await named_string_builder(bind_type, self.id, include_name=True, include_id=False)

            return (
                f"- _{prefix} {f'**{content}**' if content else ''} receive the "
                f"role{'s' if len(roles) > 1  else ''} {role_str}"
                f"{'' if len(remove_roles) == 0 else f', and have these roles removed: {remove_role_str}'}_"
            )


# TODO: Consider where to place the following utility funcs (since just dangling in binds.py is somewhat messy.)
async def named_string_builder(bind_type: str, bind_id: int, include_id: bool, include_name: bool):
    name = ""
    if include_name:
        match bind_type:
            case "group":
                try:
                    group = await groups.get_group(bind_id)
                    name = group.name
                except RobloxNotFound:
                    return f"*(Invalid Group)* ({bind_id})"

            # TODO: Logic for getting each of the item names for these types.
            case "asset":
                try:
                    asset = await assets.get_asset(bind_id)
                    name = asset.name
                except RobloxNotFound:
                    return f"*(Invalid Asset)* ({bind_id})"

            case "badge":
                try:
                    badge = await badges.get_badge(bind_id)
                    name = badge.name
                except RobloxNotFound:
                    return f"*(Invalid Badge)* ({bind_id})"

            case "gamepass":
                try:
                    gamepass = await gamepasses.get_gamepass(bind_id)
                    name = gamepass.name
                except RobloxNotFound:
                    return f"*(Invalid Gamepass)* ({bind_id})"

    id_str = str(bind_id) if not include_name else f"({bind_id})"
    return " ".join(
        [
            f"**{name}**" if include_name else "",
            id_str if include_id else "",
        ]
    ).strip()


def join_bind_strings(strings: list):
    """Helper method to use when joining all the strings for the viewbind embed."""

    # Use REPLY_CONT for all but last element
    split_strings = [f"\n{REPLY_CONT}".join(strings[:-1]), strings[-1]] if len(strings) > 2 else strings
    return f"\n{REPLY_EMOTE}".join(split_strings)
