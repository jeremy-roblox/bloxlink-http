from .models import BloxlinkGuild
import resources.users as users
from .bloxlink import instance as bloxlink
from snowfin import User
from typing import Union


async def get_linked_group_ids(guild_id: int) -> set:
    guild: BloxlinkGuild = await bloxlink.fetch_guild(str(guild_id), "roleBinds", "groupIDs")

    role_binds = guild.roleBinds or {}
    group_ids  = guild.groupIDs  or {}

    return set(group_ids.keys()).union(set(role_binds.get("groups", {}).keys()))


async def check_bind_for(roblox_account: users.RobloxAccount, bind_type: str, bind_id: str, **bind_data) -> bool:
    if bind_type == "group":
        if bind_data.get("roleset"):
            pass
        else:
            # entire group bind, find role in server with same name as their roleset
            if bind_data.get("min") and bind_data.get("max"):
                pass
            else:
                if roblox_account.groups.get(bind_id):
                    return True


    return False

async def get_binds_for(user: User, guild_id: int, roblox_account: users.RobloxAccount = None) -> dict:
    guild_binds = await bloxlink.fetch_guild(str(guild_id), "roleBinds", "groupIDs")

    if roblox_account and roblox_account.groups is None:
        await roblox_account.sync(["groups"])

    role_binds = guild_binds.binds or []

    user_binds = {
        "optional": {},
        "required": {},
    }

    # TODO: implement [un]verified roles
    # multiple verified roles

    if roblox_account:
        for bind_data in role_binds:
            bind_add_roles    = bind_data.get("roles") or []
            bind_remove_roles = bind_data.get("removeRoles") or []
            bind_nickname     = bind_data.get("nickname") or None
            role_bind         = bind_data.get("bind") or {}
            bind_criteria     = bind_data.get("criteria") or []

            bind_type         = role_bind.get("type")
            bind_id           = role_bind.get("id") or None

            if bind_criteria:
                for bind_ in bind_criteria:
                    #check_bind_for()
                    pass
            else:
                success: bool = check_bind_for(bind_type, bind_id)




    return user_binds



async def apply_binds(user: User, guild_id: int, roblox_account: users.RobloxAccount, *, moderate_user=False) -> None:
    user_binds = await get_binds_for(user, guild_id, roblox_account)

    print(user_binds)