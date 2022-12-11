from __future__ import annotations
from .models import GuildData, MISSING
import resources.users as users
import resources.groups as groups
from resources.exceptions import BloxlinkForbidden, Message
from resources.constants import DEFAULTS
from resources.secrets import BOT_API, BOT_API_AUTH
from .bloxlink import instance as bloxlink
from .utils import fetch
import hikari
import re



nickname_template_regex = re.compile(r"\{(.*?)\}")
any_group_nickname      = re.compile(r"\{group-rank-(.*?)\}")
bracket_search          = re.compile(r"\[(.*)\]")




async def parse_nickname(member: hikari.Member, template: str, roblox_user=MISSING, group: groups.RobloxGroup=MISSING, is_nickname: bool=True) -> str | None:
    template = template or DEFAULTS.get("nicknameTemplate") or ""

    if template == "{disable-nicknaming}":
        return

    guild = member.guild

    group_id = None
    group    = None
    roblox_user = roblox_user or (roblox_user is not MISSING and (await users.get_user(user=member)))

    if roblox_user is not MISSING:
        await roblox_user.sync(True)

        if group is MISSING:
            guild_data: GuildData = await bloxlink.fetch_guild_data(guild, "binds")
            group_id = any(b["bind"]["type"] == "group" for b in guild_data.binds) if guild_data.binds else None

            if group_id:
                group = roblox_user.groups.get(group_id)

        group_role = group.my_role["name"] if group else "Guest"

        # if await get_guild_value(guild, ["shorterNicknames", DEFAULTS.get("shorterNicknames")]):
        #     if group_role != "Guest":
        #         brackets_match = bracket_search.search(group_role)

        #         if brackets_match:
        #             group_role = f"[{brackets_match.group(1)}]"

        for group_id in any_group_nickname.findall(template):
            group = roblox_user.groups.get(group_id)
            group_role_from_group = group.my_role["name"] if group else "Guest"

            # if await get_guild_value(guild, ["shorterNicknames", DEFAULTS.get("shorterNicknames")]):
            #     if group_role_from_group != "Guest":
            #         brackets_match = bracket_search.search(group_role_from_group)

            #         if brackets_match:
            #             group_role_from_group = f"[{brackets_match.group(1)}]"

            template = template.replace("{group-rank-"+group_id+"}", group_role_from_group)

        if "smart-name" in template:
            if roblox_user.display_name != roblox_user.username:
                smart_name = f"{roblox_user.display_name} (@{roblox_user.username})"

                if len(smart_name) > 32:
                    smart_name = roblox_user.username
            else:
                smart_name = roblox_user.username
        else:
            smart_name = ""

        template = template.replace(
            "roblox-name", roblox_user.username
        ).replace(
            "display-name", roblox_user.display_name,
        ).replace(
            "smart-name", smart_name,
        ).replace(
            "roblox-id", str(roblox_user.id)
        ).replace(
            "roblox-age", str(roblox_user.age)
        # ).replace(
        #     "roblox-join-date", roblox_user.join_date
        ).replace(
            "group-rank", group_role
        )

    else:
        if not template:
            template: str | None = (await bloxlink.fetch_guild_data(guild, "unverifiedNickname")).unverifiedNickname

            if template == "{disable-nicknaming}":
                return

    template = template.replace(
        "discord-name", member.name
    # ).replace(
    #     "discord-nick", user.display_name
    ).replace(
        "discord-mention", member.mention
    ).replace(
        "discord-id", str(member.id)
    ).replace(
        "server-name", guild.name
    ).replace(
        "prefix", "/"
    ).replace(
        "group-url", group.url if group else ""
    ).replace(
        "group-name", group.name if group else ""
    )

    for outer_nick in nickname_template_regex.findall(template):
        nick_data = outer_nick.split(":")
        nick_fn = None
        nick_value = None

        if len(nick_data) > 1:
            nick_fn = nick_data[0]
            nick_value = nick_data[1]
        else:
            nick_value = nick_data[0]

        # nick_fn = capA
        # nick_value = roblox-name

        if nick_fn:
            if nick_fn in ("allC", "allL"):
                if nick_fn == "allC":
                    nick_value = nick_value.upper()
                elif nick_fn == "allL":
                    nick_value = nick_value.lower()

                template = template.replace("{{{0}}}".format(outer_nick), nick_value)
            else:
                template = template.replace("{{{0}}}".format(outer_nick), outer_nick) # remove {} only
        else:
            template = template.replace("{{{0}}}".format(outer_nick), nick_value)


    return template[:32] if is_nickname else template


async def apply_binds(member: hikari.Member, guild_id: hikari.Snowflake, roblox_account: users.RobloxAccount, *, moderate_user=False) -> hikari.Embed:
    if roblox_account and roblox_account.groups is None:
        await roblox_account.sync(["groups"])

    guild: hikari.guilds.RESTGuild = await bloxlink.rest.fetch_guild(guild_id)
    member_roles: dict = {}

    for member_role_id in member.role_ids:
        if role := guild.roles.get(member_role_id):
            member_roles[role.id] = {
                "id": role.id,
                "name": role.name,
                "managed": role.bot_id is None
            }

    user_binds, user_binds_response = await fetch("POST", f"{BOT_API}/binds/{member.id}", headers={"Authorization":BOT_API_AUTH}, body={
        "guild": {
            "id": guild.id,
            "roles": [{
                "id": r.id,
                "name": r.name,
                "managed": r.bot_id is None
            } for r in guild.roles.values()]
        },
        "member": {
            "id": member.id,
            "roles": member_roles
        },
        "roblox_account": roblox_account.to_dict()
    })

    if user_binds_response.status == 200:
        user_binds = user_binds["binds"]
    else:
        raise Message("Something went wrong!")

    # first apply the required binds, then ask the user if they want to apply the optional binds

    add_roles:    set = set() # used exclusively for display purposes
    remove_roles: set = set()
    possible_nicknames: list[list[hikari.Role | str]] = []
    warnings: list[str] = []
    chosen_nickname = None
    applied_nickname = None

    for required_bind in user_binds["required"]:
        # find valid roles from the server

        for bind_add_id in required_bind[1]:
            if role := guild.roles.get(bind_add_id):
                add_roles.add(role)

                if required_bind[3]:
                    possible_nicknames.append([role, required_bind[3]])

        for bind_remove_id in required_bind[2]:
            if role := guild.roles.get(bind_remove_id):
                remove_roles.add(role)

    print(add_roles)

    remove_roles   = remove_roles.difference(add_roles) # added roles get priority
    real_add_roles = add_roles.difference(set(member.roles)) # remove roles that are already on the user, also new variable so we can achieve idempotence

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
            chosen_nickname = await parse_nickname(member, chosen_nickname, roblox_account)
            # chosen_nickname_http, nickname_response = await fetch(f"{BOT_API}/nickname/parse/", headers={"Authorization":BOT_API_AUTH}, body={
            #     "user_id": member.id,
            #     "template": chosen_nickname,
            #     "roblox_account": roblox_account.to_dict()
            # })

            # if nickname_response.status == 200:
            #     chosen_nickname = chosen_nickname_http["nickname"]
            # else:
            #     raise RuntimeError(f"Nickname API returned an error: {chosen_nickname_http}")

            if guild.owner_id == member.id:
                warnings.append(f"Since you're the Server Owner, I cannot modify your nickname.\nNickname: {chosen_nickname}")
            else:

                try:
                    await member.set_nickname(chosen_nickname)
                except hikari.errors.Forbidden:
                    raise BloxlinkForbidden("I don't have permission to change the nickname of this user.")
                else:
                    applied_nickname = chosen_nickname

    if real_add_roles:
        await member.add_roles(*real_add_roles)

    if remove_roles:
        await member.remove_roles(*remove_roles)

    if add_roles or remove_roles or warnings:
        embed = hikari.Embed(
            title="Member Updated",
        )

        if add_roles:
            embed.add_field(
                name="Added Roles",
                value=",".join([r.mention for r in add_roles])
            )

        if remove_roles:
            embed.add_field(
                name="Removed Roles",
                value=",".join([r.mention for r in remove_roles])
            )

        if applied_nickname:
            embed.add_field(
                name="Nickname Changed",
                value=applied_nickname
            )

        if warnings:
            embed.add_field(
                name="Warning(s)",
                value="\n".join(warnings)
            )

    else:
        embed = hikari.Embed(
            description="No binds apply to you!"
        )

    return embed
