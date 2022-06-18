from .models import BloxlinkGuild
import resources.users as users
from .bloxlink import instance as bloxlink
from snowfin import User


async def get_linked_group_ids(guild_id: int) -> set:
    guild: BloxlinkGuild = await bloxlink.fetch_guild(str(guild_id), "roleBinds", "groupIDs")

    role_binds = guild.roleBinds or {}
    group_ids  = guild.groupIDs  or {}


    return set(group_ids.keys()).union(set(role_binds.get("groups", {}).keys()))


async def apply_binds(author: User, guild_id: int, roblox_account: users.RobloxAccount, *, moderate_user=False) -> None:
    guild_binds = await bloxlink.fetch_guild(str(guild_id), "roleBinds", "groupIDs")

    print(guild_binds)