import json
import logging
import math

import hikari

from resources.bloxlink import instance as bloxlink
from resources.exceptions import Message
from resources.models import CommandContext

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

        guild_id = ctx.interaction.guild_id
        cooldown_key = f"guild_scan:{guild_id}"

        cooldown_status = await bloxlink.redis.get(cooldown_key)
        if cooldown_status:
            cooldown_status = bytes.decode(cooldown_status)

            cooldown_time = math.ceil(await bloxlink.redis.ttl(cooldown_key) / 60)

            if not cooldown_time or cooldown_time == -1:
                await bloxlink.redis.delete(cooldown_key)
                cooldown_status = None

            match cooldown_status:
                case "1":
                    raise Message(f"This server is still queued.")
                case "2":
                    raise Message("This server's scan is currently running.")
                case "3":
                    raise Message(
                        f"This server has an ongoing cooldown! You must wait **{cooldown_time}** more minutes."
                    )

        try:
            req = await bloxlink.relay(
                "VERIFYALL",
                payload={
                    "guild_id": guild_id,
                    "channel_id": ctx.interaction.channel_id,
                    "chunk_limit": CHUNK_LIMIT,
                },
                timeout=10,
            )

            # ngl this is disgusting to do, but is required based on how .relay works.
            data = json.loads(req.get("data").decode("utf-8")).get("data")

            status = data.get("status")
            if "error" in status:
                message = data.get("message")
                logger.error(f"Gateway response error to /verifyall: {message}")

                raise Message(
                    "There was an issue when trying to update all your server members. Try again later."
                )

            # Following the pattern of the current bot which sets a key
            # to a value of 1 (queued), 2 (running), or 3 (cooldown) for scan
            # status, and then expiry is what determines the cooldown duration.
            # 24 hours by default.
            await bloxlink.redis.set(cooldown_key, "1", ex=86400)

            await ctx.response.send(content="Your server members will be updated shortly!")
        except (RuntimeError, TimeoutError) as ex:
            logger.error(f"An issue was encountered contacting the gateway - {ex};{ex.__cause__}")
            raise Message(
                "There was an issue when trying to update all your server members. Try again later."
            )
