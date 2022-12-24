from resources.bloxlink import instance as bloxlink
import resources.binds as binds
import resources.users as users
from resources.models import CommandContext
from resources.exceptions import UserNotVerified, Message
import hikari


@bloxlink.command(
    category="Administration",
    defer=True,
    permissions=hikari.Permissions.MANAGE_GUILD

)
class BindCommand:
    """bind Discord role(s) to Roblox entities"""

    @bloxlink.subcommand()
    async def group(self, ctx: CommandContext):
        """bind a group to your server"""

        print("group subcommand")
        await ctx.response.send("from group subcommand")
