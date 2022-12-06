from resources.bloxlink import instance as bloxlink
from resources.models import CommandContext


@bloxlink.command(
    category="Miscellaneous",
    defer=True
)
class PingCommand():
    """A module that responds to ping commands"""

    async def __main__(self, ctx: CommandContext):
        """check if the bot is alive"""

        await ctx.response.send("pong")
        await ctx.response.send("pong")

