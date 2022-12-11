
import resources.binds as binds
import resources.users as users
from resources.exceptions import UserNotVerified
from resources.bloxlink import instance as bloxlink
from resources.models import CommandContext


@bloxlink.command(
    category="Account",
    defer=True
)
class VerifyCommand:
    """link your Roblox account to your Discord account and get your server roles"""

    async def __main__(self, ctx: CommandContext):
        roblox_account = await users.get_user_account(ctx.user, raise_errors=False)
        message_response = await binds.apply_binds(ctx.member, ctx.guild_id, roblox_account, moderate_user=True)

        if not roblox_account:
            print("not verified")
