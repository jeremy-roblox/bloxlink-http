import json
import logging
import math
from datetime import datetime

import hikari

from resources.bloxlink import instance as bloxlink
from resources.exceptions import Message
from bloxlink_lib import BaseModel, parse_into
from bloxlink_lib.database import redis
from resources.commands import CommandContext, GenericCommand
from resources.ui.components import Button, CommandCustomID, component_author_validation
from resources.ui import ProgressBar

logger = logging.getLogger("verify_all")
CHUNK_LIMIT = 1000


class Response(BaseModel):
    success: bool
    nonce: str = None

class ProgressCustomID(CommandCustomID):
    nonce: str

class VerifyAllProgress(BaseModel):
    started: datetime
    members_processed: int
    total_members: int
    current_chunk: int
    total_chunks: int



@component_author_validation(parse_into=ProgressCustomID, defer=False)
async def get_progress(ctx: CommandContext, custom_id: ProgressCustomID):
    nonce = custom_id.nonce
    progress: dict | None = json.loads(await redis.get(f"progress:{nonce}")) if await redis.exists(f"progress:{nonce}") else None

    response = ctx.response

    if not progress:
        await response.send("No progress has been made yet.", ephemeral=True)
        return

    parsed_progress = parse_into(progress, VerifyAllProgress)

    embed = hikari.Embed(
        title="Progress Update",
        description=(
            f"Started: {parsed_progress.started}\n"
            f"Members processed: {parsed_progress.members_processed}/{parsed_progress.total_members}\n"
            f"Chunks processed: {parsed_progress.current_chunk}/{parsed_progress.total_chunks}\n" +
            "Progress: " + str(ProgressBar(progress=parsed_progress.members_processed, total=parsed_progress.total_members))
        )
    )

    await response.send(embed=embed, ephemeral=True)



@bloxlink.command(
    category="Premium",
    premium=True,
    defer=True,
    permissions=hikari.Permissions.MANAGE_GUILD | hikari.Permissions.MANAGE_ROLES,
    accepted_custom_ids={
        "verifyall:verifyall_button": get_progress
    }
)
class VerifyallCommand(GenericCommand):
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

        response = ctx.response

        # cooldown_status = await bloxlink.redis.get(cooldown_key)
        # if cooldown_status:
        #     cooldown_status = bytes.decode(cooldown_status)

        #     cooldown_time = math.ceil(await bloxlink.redis.ttl(cooldown_key) / 60)

        #     if not cooldown_time or cooldown_time == -1:
        #         await bloxlink.redis.delete(cooldown_key)
        #         cooldown_status = None

        #     match cooldown_status:
        #         case "1":
        #             raise Message("This server is still queued.")
        #         case "2":
        #             raise Message("This server's scan is currently running.")
        #         case "3":
        #             raise Message(
        #                 f"This server has an ongoing cooldown! You must wait **{cooldown_time}** more minutes."
        #             )

        progress_responses = await bloxlink.relay(
            "VERIFYALL",
            model=Response,
            payload={
                "guild_id": guild_id,
                "channel_id": ctx.interaction.channel_id,
                "chunk_limit": CHUNK_LIMIT,
            },
            timeout=10,
            wait_for_all=False,
        )

        progress_response = progress_responses[0] if progress_responses else None

        if not progress_response:
            raise Message(
                "There was an issue when trying to update all your server members. Try again later."
            )

        embed = hikari.Embed(
            title="Now Updating Everyone...",
            description="Your server members will be updated shortly!\nPlease feel free to press the Progress button for the latest progress.",
        )

        components = [
            Button(
                label="Progress",
                custom_id=str(ProgressCustomID(
                    nonce=progress_response.nonce,
                    command_name="verifyall",
                    user_id=ctx.user.id,
                    section="verifyall_button")
                ),
            ),
            Button(
                label="Stop Scan",
                custom_id=str(ProgressCustomID(
                    nonce=progress_response.nonce,
                    command_name="verifyall",
                    user_id=ctx.user.id,
                    section="verifyall_cancel_button")
                ),
                style=Button.ButtonStyle.DANGER
            )
        ]

        await response.send(embed=embed, components=components)

        #     # ngl this is disgusting to do, but is required based on how .relay works.
        #     data = json.loads(req.get("data").decode("utf-8")).get("data")

        #     status = data.get("status")
        #     if "error" in status:
        #         message = data.get("message")
        #         logger.error(f"Gateway response error to /verifyall: {message}")

        #         raise Message(
        #             "There was an issue when trying to update all your server members. Try again later."
        #         )

        #     # Following the pattern of the current bot which sets a key
        #     # to a value of 1 (queued), 2 (running), or 3 (cooldown) for scan
        #     # status, and then expiry is what determines the cooldown duration.
        #     # 24 hours by default.
        #     await bloxlink.redis.set(cooldown_key, "1", ex=timedelta(days=1).seconds)

        #     await ctx.response.send(content="Your server members will be updated shortly!")
        # except (RuntimeError, TimeoutError) as ex:
        #     logger.error(f"An issue was encountered contacting the gateway - {ex};{ex.__cause__}")
        #     raise Message(
        #         "There was an issue when trying to update all your server members. Try again later."
        #     ) from None
