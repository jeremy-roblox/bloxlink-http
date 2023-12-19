from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext
from resources.response import Prompt, Response, PromptPageData
from resources.components import Component


@bloxlink.command(
    category="Miscellaneous",
)
class PingCommand:
    """check if the bot is alive"""

    async def __main__(self, ctx: CommandContext):
        yield await ctx.response.send_first("pong")
