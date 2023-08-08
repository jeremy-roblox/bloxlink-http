from resources.bloxlink import instance as bloxlink
from resources.models import CommandContext


@bloxlink.command(category="Miscellaneous")
class PingCommand:
    """check if the bot is alive"""

    async def __main__(self, ctx: CommandContext):
        await ctx.response.send("pong")
