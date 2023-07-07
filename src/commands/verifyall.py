from resources.bloxlink import instance as bloxlink
from resources.models import CommandContext
import hikari
import logging

logger = logging.getLogger("verify_all")


@bloxlink.command(
    category="Administration",
    defer=True,
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

        try:
            await bloxlink.relay(
                "VERIFYALL", payload={"guild_id": ctx.guild_id, "channel_id": ctx.interaction.channel_id}
            )

            await ctx.response.send(content="Server will start being scanned soon:tm:.")
        except (RuntimeError, TimeoutError) as ex:
            await ctx.response.send(
                content="There was an issue when starting to scan your server. Try again later."
            )
            logger.error(f"An issue was encountered contacting the gateway - {ex}")

        # Use to confirm if the server got the request or not
        # yes: send next resposne, no: explode the world (say there was an issue, try later)
