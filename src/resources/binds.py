from .models import BloxlinkGuild
import resources.users as users
import resources.groups as groups
from .bloxlink import instance as bloxlink
from snowfin import User


async def get_linked_group_ids(guild_id: int) -> set:
    guild: BloxlinkGuild = await bloxlink.fetch_guild(str(guild_id), "roleBinds", "groupIDs")

    role_binds: dict = guild.roleBinds or {}
    group_ids:  dict  = guild.groupIDs or {}

    return set(group_ids.keys()).union(set(role_binds.get("groups", {}).keys()))


def check_bind_for(guild_roles: list, roblox_account: users.RobloxAccount, bind_type: str, bind_id: str, **bind_data) -> bool:
    bind_roles = []

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
                            bind_roles.append(role)

                    return True, bind_roles


    return False, bind_roles

async def get_binds_for(user: User, guild_id: int, roblox_account: users.RobloxAccount = None) -> dict:
    guild_binds = await bloxlink.fetch_guild(str(guild_id), "binds")
    role_binds = guild_binds.binds or []

    user_binds = {
        "optional": [],
        "required": [],
    }

    guild_roles = await bloxlink.fetch_roles(guild_id)
    # print(guild_roles)

    if roblox_account and roblox_account.groups is None:
        await roblox_account.sync(["groups"])

    # TODO: implement [un]verified roles
    # multiple verified roles

    if roblox_account:
        for bind_data in role_binds:
            # bind_add_roles    = bind_data.get("roles") or []
            # bind_remove_roles = bind_data.get("removeRoles") or []
            # bind_nickname     = bind_data.get("nickname") or None
            role_bind         = bind_data.get("bind") or {}
            bind_criteria     = bind_data.get("criteria") or []
            bind_required     = not bind_data.get("optional", False)

            bind_type         = role_bind.get("type")
            bind_id           = role_bind.get("id") or None

            success: bool = False
            bind_roles: list = []

            if bind_criteria:
                for bind_ in bind_criteria:
                    #check_bind_for()
                    raise NotImplementedError()
            else:
                success, bind_roles = check_bind_for(guild_roles, roblox_account, bind_type, bind_id)
                # print(bind_roles)


            if success:
                if bind_required:
                    user_binds["required"].append([bind_data, bind_roles])
                else:
                    user_binds["optional"].append([bind_data, bind_roles])


    return user_binds



async def apply_binds(user: User, guild_id: int, roblox_account: users.RobloxAccount, *, moderate_user=False) -> None:
    user_binds = await get_binds_for(user, guild_id, roblox_account)

    print(user_binds)

    # first apply the required binds, then ask the user if they want to apply the optional binds

    add_roles = []
    remove_roles = []

    for required_bind in user_binds["required"]:
        pass
