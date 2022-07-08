from .models import BloxlinkGuild
import resources.users as users
import resources.groups as groups
from .bloxlink import instance as bloxlink
from snowfin import Member, Embed, EmbedField
from typing import Optional


async def get_linked_group_ids(guild_id: int) -> set:
    guild: BloxlinkGuild = await bloxlink.fetch_guild(str(guild_id), "roleBinds", "groupIDs")

    role_binds: dict = guild.roleBinds or {}
    group_ids:  dict  = guild.groupIDs or {}

    return set(group_ids.keys()).union(set(role_binds.get("groups", {}).keys()))


def check_bind_for(guild_roles: list, roblox_account: users.RobloxAccount, bind_type: str, bind_id: str, **bind_data) -> tuple[bool, set, set]:
    bind_roles:   set  = set()
    remove_roles: set  = set()

    success: bool = False

    if bind_type == "group":
        if bind_data.get("roleset"):
            raise NotImplementedError()
        else:
            # entire group bind, find role in server with same name as their roleset
            user_group: groups.RobloxGroup = roblox_account.groups.get(bind_id)

            if user_group:
                if bind_data.get("min") and bind_data.get("max"):
                    raise NotImplementedError()
                else:
                    for role in guild_roles:
                        if role["managed"] == False and user_group.rolesets.get(role["name"]):
                            bind_roles.add(role["id"])
                            break

                    success = True


    if success:
        # add in the remove roles
        if bind_data.get("removeRoles"):
            remove_roles.update(bind_data["removeRoles"])

    return success, bind_roles, remove_roles

async def get_binds_for(member: Member, guild_id: int, roblox_account: users.RobloxAccount = None) -> dict:
    guild_binds: dict = await bloxlink.fetch_guild(str(guild_id), "binds")
    role_binds: list  = guild_binds.binds or []

    user_binds = {
        "optional": [],
        "required": [],
    }

    guild_roles: list = await bloxlink.fetch_roles(guild_id)
    # print(guild_roles)

    if roblox_account and roblox_account.groups is None:
        await roblox_account.sync(["groups"])

    # TODO: implement [un]verified roles
    # multiple verified roles

    if roblox_account:
        for bind_data in role_binds:
            # bind_nickname     = bind_data.get("nickname") or None
            role_bind: dict      = bind_data.get("bind") or {}
            bind_criteria: list  = bind_data.get("criteria") or []
            bind_required: bool  = not bind_data.get("optional", False)

            bind_type: str         = role_bind.get("type")
            bind_id: Optional[str] = role_bind.get("id") or None

            success: bool = False
            bind_roles: list = []
            bind_remove_roles: list = []

            if bind_criteria:
                for bind_ in bind_criteria:
                    #check_bind_for()
                    raise NotImplementedError()
            else:
                success, bind_roles, bind_remove_roles = check_bind_for(guild_roles, roblox_account, bind_type, bind_id)
                # print(bind_roles)

            if success:
                if bind_required:
                    user_binds["required"].append([bind_data, bind_roles, bind_remove_roles])
                else:
                    user_binds["optional"].append([bind_data, bind_roles, bind_remove_roles])


    return user_binds



async def apply_binds(member: Member, guild_id: int, roblox_account: users.RobloxAccount, *, moderate_user=False) -> dict:
    user_binds: dict = await get_binds_for(member, guild_id, roblox_account)

    print(user_binds)

    # first apply the required binds, then ask the user if they want to apply the optional binds

    add_roles:    set = set()
    remove_roles: set = set()

    for required_bind in user_binds["required"]:
        add_roles.update(required_bind[1])
        remove_roles.update(required_bind[2])

    if user_binds.get("optional"):
        raise NotImplementedError()

    remove_roles = remove_roles.difference(add_roles) # added roles get priority
    add_roles    = add_roles.difference(set([str(r) for r in member.roles])) # remove roles that are already on the user

    if add_roles or remove_roles:
        await bloxlink.edit_user_roles(member, guild_id, add_roles=add_roles, remove_roles=remove_roles)

        embed = Embed(
            description="this is temp until we add profile cards back"
        )

        if add_roles:
            embed.add_field(name="Added Roles", value=",".join([f"<@&{r}>" for r in add_roles]))

        if remove_roles:
            embed.add_field(name="Removed Roles", value=",".join([f"<@&{r}>" for r in remove_roles]))

    else:
        embed = Embed(
            description="You're already up-to-date with the roles for this server. No changes were made."
        )

    return embed
