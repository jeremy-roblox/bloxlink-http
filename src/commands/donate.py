import hikari
from hikari import Embed

from resources.bloxlink import instance as bloxlink
from resources.models import CommandContext


@bloxlink.command()
class DonateCommand:
    """Learn how to receive Bloxlink Premium"""

    async def __main__(self, ctx: CommandContext):
        target_user = ctx.user

        embed = Embed(
            title="Bloxlink Premium", description="Premium purchases help support Bloxlink!", color=0x00B2FF
        )

        embed.add_field(
            name="Server Premium",
            value="Unlocks premium commands, lessens restrictions, no ads for your server verification page, and more for your server.",
            inline=False,
        )

        button_menu = (
            bloxlink.rest.build_message_action_row()
            .add_button(
                hikari.ButtonStyle.LINK,
                f"https://blox.link/dashboard/guilds/{ctx.guild_id}/premium"
                if ctx.guild_id
                else "https://blox.link/",
            )
            .set_label("Click for Server Premium")
            .add_to_container()
        )

        await ctx.response.send(embed=embed, components=button_menu)
