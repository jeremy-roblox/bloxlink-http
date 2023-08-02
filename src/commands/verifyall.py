from resources.bloxlink import instance as bloxlink
from resources.exceptions import Message
from resources.models import CommandContext
import hikari
import logging
import json

logger = logging.getLogger("verify_all")
CHUNK_LIMIT = 1000


@bloxlink.command(
    category="Premium",
    defer=True,
    permissions=hikari.Permissions.MANAGE_GUILD | hikari.Permissions.MANAGE_ROLES,
)
class VerifyallCommand:
    """Update everyone in your server"""

    async def __main__(self, ctx: CommandContext):
        """
        Sets up a scan to update everyone in a guild.

        Makes a request to the gateway over redis to chunk the guild members.
        The gateway then will sent a request to the update endpoint (endpoints/update_user.py)
        where the users will then be handled to be updated.
        """
        try:
            req = await bloxlink.relay(
                "VERIFYALL",
                payload={
                    "guild_id": ctx.interaction.guild_id,
                    "channel_id": ctx.interaction.channel_id,
                    "chunk_limit": CHUNK_LIMIT,
                },
            )

            # ngl this is disgusting to do, but is required based on how .relay works.
            data = req.get("data")
            data = data.decode("utf-8")
            data = json.loads(data)
            data = data.get("data")

            status = data.get("status")
            if "error" in status:
                message = data.get("message")
                logger.error(f"Gateway response error to /verifyall: {message}")
                raise Message(
                    "There was an issue when trying to update all your server members. Try again later."
                )

            await ctx.response.send(content="Your server members will be updated shortly!")
        except (RuntimeError, TimeoutError) as ex:
            logger.error(f"An issue was encountered contacting the gateway - {ex};{ex.__cause__}")
            raise Message(
                "There was an issue when trying to update all your server members. Try again later."
            )
