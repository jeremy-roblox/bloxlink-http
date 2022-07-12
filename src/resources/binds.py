from .models import GuildData
import resources.users as users
import resources.groups as groups
from .bloxlink import instance as bloxlink
import snowfin
from typing import Any


async def get_linked_group_ids(guild_id: int) -> set:
    guild: GuildData = await bloxlink.fetch_guild_data(str(guild_id), "roleBinds", "groupIDs")

    role_binds: dict  = guild.roleBinds or {}
    group_ids:  dict  = guild.groupIDs or {}

    return set(group_ids.keys()).union(set(role_binds.get("groups", {}).keys()))


async def get_default_verified_role(guild_id: int, guild_roles: dict[str, dict[str, Any]] = None) -> tuple[str, str]:
    if not guild_roles:
        guild_roles: list = await bloxlink.fetch_roles(guild_id)

    guild_data: GuildData = await bloxlink.fetch_guild_data(str(guild_id), "verifiedRoleEnabled", "verifiedRole", "verifiedRoleName", "unverifiedRoleEnabled", "unverifiedRole", "unverifiedRoleName")

    verified_role:   str | None = None
    unverified_role: str | None = None

    verified_role_name:   str | None  = None if guild_data.verifiedRole else guild_data.verifiedRoleName or "Verified"
    unverified_role_name: str | None  = None if guild_data.unverifiedRole else guild_data.unverifiedRoleName or "Unverified"

    if guild_data.verifiedRoleEnabled or guild_data.unverifiedRoleEnabled:
        for role in guild_roles.values():
            if role["managed"] == False:
                if role["name"] == verified_role_name or role["id"] == guild_data.verifiedRole:
                    verified_role = role["id"]
                elif role["name"] == unverified_role_name or role["id"] == guild_data.unverifiedRole:
                    unverified_role = role["id"]

    return verified_role, unverified_role

def flatten_binds(role_binds: list) -> list:
    all_binds: list = []

    for bind in role_binds:
        if bind.get("bind", {}).get("criteria"):
            map(all_binds.append, bind["bind"]["criteria"])
        else:
            all_binds.append(bind["bind"])

    return all_binds

def has_custom_verified_roles(role_binds: list) -> tuple[bool, bool]:
    has_verified_role:   bool = False
    has_unverified_role: bool = False

    all_binds: list = flatten_binds(role_binds)

    for bind in all_binds:
        if bind.get("type") == "verified":
            has_verified_role = True
        elif bind.get("type") == "unverified":
            has_unverified_role = True

    return has_verified_role, has_unverified_role

async def check_bind_for(guild_roles: dict[str, dict[str, Any]], guild_id: int, roblox_account: users.RobloxAccount, bind_type: str, bind_id: str, **bind_data) -> tuple[bool, set, set]:
    bind_roles:   set  = set()
    remove_roles: set  = set()

    success: bool = False
    entire_group_bind: bool = "roles" not in bind_data # find a role matching their roleset
    user_group: groups.RobloxGroup | None = roblox_account.groups.get(bind_id) if roblox_account else None

    if bind_type == "group":
        if roblox_account:
            user_group: groups.RobloxGroup = roblox_account.groups.get(bind_id)

            if user_group:
                if bind_data.get("roleset"):
                    bind_roleset = bind_data["roleset"]

                    if bind_roleset == user_group.my_role["rank"] or (bind_roleset < 0 and abs(bind_roleset) <= user_group.my_role["rank"]):
                        success = True

                elif bind_data.get("min") and bind_data.get("max"):
                    if int(bind_data["min"]) <= user_group.my_role["rank"] <= int(bind_data["max"]):
                        success = True

                # elif bind_data.get("everyone"):
                #     success = True
                else:
                    success = True


            else:
                # check if guest bind (not in group)
                if bind_data.get("guest"):
                    success = True

    elif bind_type in ("verified", "unverified"):
        if bind_type == "verified" and roblox_account:
            success = True
        elif bind_type == "unverified" and not roblox_account:
            success = True

        for bind_role_id in bind_data.get("roles", []):
            if bind_role_id in guild_roles:
                if bind_type == "verified" and roblox_account:
                    bind_roles.add(bind_role_id)
                elif bind_type == "unverified" and not roblox_account:
                    bind_roles.add(bind_role_id)

    if success:
        if entire_group_bind and not (roblox_account and user_group):
            raise RuntimeError("Bad bind: this bind must have roles if the user does not have a Roblox account.")

        # add in the remove roles
        if bind_data.get("removeRoles"):
            remove_roles.update(bind_data["removeRoles"])

        if entire_group_bind:
            # find role that matches their roleset
            for role in guild_roles.values():
                if role["managed"] == False and user_group.my_role["name"] == role["name"]:
                    bind_roles.add(role["id"])

                    break
            else:
                # role was not found in server, so we need to create it
                # TODO: check for dynamic roles?
                # TODO: check for permissions
                role = await bloxlink.create_role(guild_id, user_group.my_role["name"])
                bind_roles.add(role["id"])

        else:
            # just add in the bind roles
            bind_roles.update(bind_data["roles"])

        if bind_data.get("roles"):
            bind_roles.update(bind_data["roles"])

    return success, bind_roles, remove_roles

async def get_binds_for(member: snowfin.Member, guild_id: int, roblox_account: users.RobloxAccount = None) -> dict:
    guild_data: GuildData = await bloxlink.fetch_guild_data(str(guild_id), "binds")

    role_binds: list = guild_data.binds or []

    user_binds = {
        "optional": [],
        "required": [],
    }

    guild_roles: dict[str, dict[str, Any]] = await bloxlink.fetch_roles(guild_id)

    if roblox_account and roblox_account.groups is None:
        await roblox_account.sync(["groups"])

    for bind_data in role_binds:
        # bind_nickname     = bind_data.get("nickname") or None
        role_bind: dict      = bind_data.get("bind") or {}
        bind_required: bool  = not bind_data.get("optional", False)

        bind_type: str         = role_bind.get("type")
        bind_id:   str | None  = role_bind.get("id") or None
        bind_criteria: list  = role_bind.get("criteria") or []

        bind_success: bool = None
        bind_roles: list = []
        bind_remove_roles: list = []

        if bind_criteria:
            for criterion in bind_criteria:
                criterion_success, bind_roles, bind_remove_roles = await check_bind_for(guild_roles, guild_id, roblox_account, criterion["type"], criterion["id"], **bind_data, **criterion)

                if bind_type == "requireAll":
                    if bind_success is None and criterion_success is True:
                        bind_success = True
                    elif bind_success is True and criterion_success is False:
                        bind_success = False
        else:
            bind_success, bind_roles, bind_remove_roles = await check_bind_for(guild_roles, guild_id, roblox_account, bind_type, bind_id, **role_bind, **bind_data)

        if bind_success:
            if bind_required:
                user_binds["required"].append([bind_data, bind_roles, bind_remove_roles])
            else:
                user_binds["optional"].append([bind_data, bind_roles, bind_remove_roles])

    # for when they didn't save their own [un]verified roles
    has_verified_role, has_unverified_role = has_custom_verified_roles(role_binds)

    if not (has_verified_role and has_unverified_role):
        # no? then we can check for the default [un]verified roles
        verified_role, unverified_role = await get_default_verified_role(guild_id, guild_roles=guild_roles)

        if not has_verified_role and verified_role and roblox_account:
            user_binds["required"].append([{"type": "verified"}, [verified_role], [unverified_role] if unverified_role and unverified_role in member.roles else []])

        if not has_unverified_role and unverified_role and not roblox_account:
            user_binds["required"].append([{"type": "unverified"}, [unverified_role], [verified_role] if verified_role and verified_role in member.roles else []])


    return user_binds



async def apply_binds(member: snowfin.Member, guild_id: int, roblox_account: users.RobloxAccount, *, moderate_user=False) -> dict:
    user_binds: dict = await get_binds_for(member, guild_id, roblox_account)

    # first apply the required binds, then ask the user if they want to apply the optional binds

    add_roles:    set = set() # used exclusively for display purposes
    remove_roles: set = set()

    for required_bind in user_binds["required"]:
        add_roles.update(required_bind[1])
        remove_roles.update(required_bind[2])

    if user_binds.get("optional"):
        raise NotImplementedError()

    remove_roles   = remove_roles.difference(add_roles) # added roles get priority
    real_add_roles = add_roles.difference(set([str(r) for r in member.roles])) # remove roles that are already on the user, also new variable so we can achieve idempotence

    if real_add_roles or remove_roles:
        await bloxlink.edit_user_roles(member, guild_id, add_roles=add_roles, remove_roles=remove_roles)

    if add_roles or remove_roles:
        embed = snowfin.Embed(
            description="this is temp until we add profile cards back"
        )

        if add_roles:
            embed.add_field(
                name="Added Roles",
                value=",".join([f"<@&{r}>" for r in add_roles])
            )

        if remove_roles:
            embed.add_field(
                name="Removed Roles",
                value=",".join([f"<@&{r}>" for r in remove_roles])
            )

    else:
        embed = snowfin.Embed(
            description="No binds apply to you!"
        )

    return embed
