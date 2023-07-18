from resources.bloxlink import instance as bloxlink
from resources.models import CommandContext
import hikari
import logging
import json

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
            req = await bloxlink.relay(
                "VERIFYALL",
                payload={"guild_id": ctx.interaction.guild_id, "channel_id": ctx.interaction.channel_id},
            )

            # ngl this is disgusting to do, but is required based on how .relay works.
            data = req.get("data")
            data = data.decode("utf-8")
            data = json.loads(data)
            data = data.get("data")

            status = data.get("status")
            if "error" in status:
                errors = data.get("errors")
                logger.error(f"Gateway response error to /verifyall: {errors}")
                await ctx.response.send(
                    content="There was an issue when trying to update all your server members. Try again later."
                )
                return

            await ctx.response.send(content="Your server members will be updated shortly!")
        except (RuntimeError, TimeoutError) as ex:
            await ctx.response.send(
                content="There was an issue when starting to scan your server. Try again later."
            )
            logger.error(f"An issue was encountered contacting the gateway - {ex};{ex.__cause__}")
