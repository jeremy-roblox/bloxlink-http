from resources.bloxlink import instance as bloxlink
from resources.models import CommandContext
from hikari import Embed, EmbedField


@bloxlink.command()
class InviteCommand():

    async def __main__(self, ctx: CommandContext):
        """invite the bot to your server"""

        await ctx.response.send(embed=
            Embed(
                title="Test"
            )
        )

        await ctx.response.send(embed=
            Embed(
                title="Test"
            )
        )
