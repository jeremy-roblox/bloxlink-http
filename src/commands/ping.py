from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext


@bloxlink.command(
    category="Miscellaneous",
)
class PingCommand:
    """check if the bot is alive"""

    async def __main__(self, ctx: CommandContext):
        return await ctx.response.send_first("pong")
