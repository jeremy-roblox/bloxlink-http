from __future__ import annotations
from .models import BaseGuildBind, GuildData, MISSING
import resources.users as users
import resources.groups as groups
from resources.exceptions import BloxlinkException, BloxlinkForbidden, Message
from resources.constants import DEFAULTS
from resources.secrets import BOT_API, BOT_API_AUTH
from .bloxlink import instance as bloxlink
from .utils import fetch
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


async def get_bind_desc(guild_id: int | str, group_id: int | str = None):
    return "TODO: show existing binds"


async def create_bind(
    guild_id: int | str,
    bind_type: str["group" | "asset" | "gamepass" | "badge"],
    bind_id: int = None,
    roles: list[str] = None,
    remove_roles: list[str] = None,
    nickname: str = None,
    **bind_data,
):
    """creates a new guild bind. if it already exists, the roles will be appended"""

    guild_binds: GuildData = (await bloxlink.fetch_guild_data(str(guild_id), "binds")).binds

    existing_binds = list(
        filter(
            lambda b: b["bind"]["type"] == bind_type
            and (b["bind"].get("id") == bind_id if bind_id else True),
            guild_binds,
        )
    )

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
            raise NotImplementedError()
        else:
            if roles:
                # TODO: compare current role IDs with the server and remove invalid roles
                existing_binds[0]["roles"] = list(
                    set(existing_binds[0].get("roles", []) + roles)
                )  # add roles and removes duplicates
            else:
                raise NotImplementedError()
    else:
        # everything else
        raise NotImplementedError()


async def apply_binds(
    member: hikari.Member,
    guild_id: hikari.Snowflake,
    roblox_account: users.RobloxAccount = None,
    *,
    moderate_user=False,
) -> hikari.Embed:
    if roblox_account and roblox_account.groups is None:
        await roblox_account.sync(["groups"])

    guild: hikari.guilds.RESTGuild = await bloxlink.rest.fetch_guild(guild_id)
    member_roles: dict = {}

    for member_role_id in member.role_ids:
        if role := guild.roles.get(member_role_id):
            member_roles[role.id] = {
                "id": role.id,
                "name": role.name,
                "managed": bool(role.bot_id) and role.name != "@everyone",
            }

    user_binds, user_binds_response = await fetch(
        "POST",
        f"{BOT_API}/binds/{member.id}",
        headers={"Authorization": BOT_API_AUTH},
        body={
            "guild": {
                "id": guild.id,
                "roles": [
                    {"id": r.id, "name": r.name, "managed": bool(r.bot_id) and role.name != "@everyone"}
                    for r in guild.roles.values()
                ],
            },
            "member": {"id": member.id, "roles": member_roles},
            "roblox_account": roblox_account.to_dict() if roblox_account else None,
        },
    )

    if user_binds_response.status == 200:
        user_binds = user_binds["binds"]
    else:
        raise Message("Something went wrong!")

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
                    "user_data": {"name": member.username, "nick": member.nickname, "id": member.id},
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

            if guild.owner_id == member.id:
                warnings.append(
                    f"Since you're the Server Owner, I cannot modify your nickname.\nNickname: {chosen_nickname}"
                )
            else:
                try:
                    await member.edit(nickname=chosen_nickname)
                except hikari.errors.ForbiddenError:
                    warnings.append("I don't have permission to change the nickname of this user.")
                else:
                    applied_nickname = chosen_nickname

    try:
        if add_roles or remove_roles:
            # since this overwrites their roles, we need to add in their current roles
            # then, we remove the remove_roles from the set
            await member.edit(
                roles=set(getattr(r, "id", r) for r in add_roles + member.role_ids).difference(
                    [r.id for r in remove_roles]
                )
            )

    except hikari.errors.ForbiddenError:
        raise BloxlinkForbidden("I don't have permission to add roles to this user.")

    if add_roles or remove_roles or warnings:
        embed = hikari.Embed(
            title="Member Updated",
        )
        embed.set_author(
            name=str(member),
            icon=member.display_avatar_url.url,
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


class GuildBind(BaseGuildBind):
    def determine_type(self) -> str:
        if self.type == "group":
            if not self.roles or self.roles in ("undefined", "null"):
                return "linked_group"
            else:
                return "group_roles"
        else:
            return self.type

    async def get_bind_string(self, guild_id: int, include_id=True, group_data=None) -> str:
        role_string = await bloxlink.role_ids_to_names(guild_id=guild_id, roles=self.roles)
        remove_role_str = ""
        if self.removeRoles:
            remove_role_str = f"**Remove Roles:** {await bloxlink.role_ids_to_names(guild_id=guild_id, roles=self.removeRoles)}"

        bind_string_list = []

        if self.type == "group":
            if not group_data:
                raise BloxlinkException("Group data needs to be given if the type is a group.")

            group_id_string = f"**Group:** {group_data.name} ({self.id})" if include_id else ""

            # Entire group binding.
            if not self.roles or self.roles == "undefined" or self.roles == "null":
                bind_string_list.append(
                    f"{group_id_string} {f' → **Nickname:** {self.nickname}' if self.nickname else ''}"
                )
            else:
                # Every other group binding type (range, guest, everyone, single ID)
                output_list = []

                base_string = group_id_string
                rank_string = ""
                role_string = f"**Role(s):** {role_string}"

                nickname_string = f"**Nickname:** {self.nickname}" if self.nickname else ""

                if self.min is not None and self.max is not None:
                    rank_string = f"**Rank Range:** {self.min} to {self.max}"

                elif self.roleset is not None:
                    rank_string = f"**Rank:** {self.roleset}"

                elif self.everyone:
                    rank_string = "**Rank:** All group members"

                elif self.guest:
                    rank_string = "**Rank:** Non-group members"

                # Append only accepts one value at a time, so do this.
                if base_string:
                    output_list.append(base_string)
                output_list.append(rank_string)
                output_list.append(role_string)
                if nickname_string:
                    output_list.append(nickname_string)

                bind_string_list.append(" → ".join(output_list))
        elif self.type == "asset":
            # TODO: Put asset name in string.
            bind_string_list.append(
                f"{f'**Asset ID:** {self.id} → ' if include_id else ''}"
                f"**Nickname:** {self.nickname} → **Role(s):** {role_string}"
            )
        elif self.type == "badge":
            # TODO: Put badge name in string.
            bind_string_list.append(
                f"{f'**Badge ID:** {self.id} → ' if include_id else ''}"
                f"**Nickname:** {self.nickname} → **Role(s):** {role_string}"
            )
        elif self.type == "gamepass":
            # TODO: Put gamepass name in string.
            bind_string_list.append(
                f"{f'**Gamepass ID:** {self.id} → ' if include_id else ''}"
                f"**Nickname:** {self.nickname} → **Role(s):** {role_string}",
            )
        else:
            return "No valid binding type was given. How? No clue."

        if remove_role_str:
            bind_string_list.append(remove_role_str)
        return " → ".join(bind_string_list)
