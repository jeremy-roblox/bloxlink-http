from .models import BloxlinkGuild
from .bloxlink import instance as bloxlink


async def get_linked_group_ids(guild_id: int) -> set:
    guild: BloxlinkGuild = await bloxlink.fetch_guild(str(guild_id), "roleBinds", "groupIDs")

    role_binds = guild.roleBinds or {}
    group_ids  = guild.groupIDs  or {}


    return set(group_ids.keys()).union(set(role_binds.get("groups", {}).keys()))

