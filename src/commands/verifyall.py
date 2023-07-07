from resources.bloxlink import instance as bloxlink
from resources.models import CommandContext
import hikari


@bloxlink.command(
    category="Administration",
    permissions=hikari.Permissions.MANAGE_GUILD | hikari.Permissions.MANAGE_ROLES,
)
class VerifyallCommand:
    """Update everyone in your server"""

    async def __main__(self, ctx: CommandContext):
        """
        Flow concept:
            - User runs verifyall
            - Request sent to gateway
                - Gateway chunks the server
                - Sends requests to an endpoint of HTTP server (this) to update the user(s)
                Repeat request sending until user list is empty

        Initial request information:
            - Server ID, channel ID?
                Server ID - so we know which guild to chunk and update people in
                Channel ID - have the gateway send a message when the scan is done
                    saying that the scan is complete?
        """

        await ctx.response.send(content="Server will start being scanned soon:tm:.")
