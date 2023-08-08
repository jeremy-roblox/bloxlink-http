from hikari import Embed, EmbedField

from resources.bloxlink import instance as bloxlink
from resources.models import CommandContext


@bloxlink.command()
class InviteCommand:
    """invite the bot to your server"""

    async def __main__(self, ctx: CommandContext):
        embed = Embed(title="hello")
        await ctx.response.send(embed=embed)
