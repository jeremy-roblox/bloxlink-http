from ..models import RobloxAccount, BloxlinkUser
from snowfin import User
from ..bloxlink import instance as bloxlink



async def get_user_account(user: User, guild_id: int = None) -> RobloxAccount:
    """get a user's linked Roblox account"""

    bloxlink_user: BloxlinkUser = await bloxlink.fetch_user(str(user.id), "robloxID", "robloxAccounts")
