from resources.structures.Bloxlink import Bloxlink
from resources.constants import LIMITS
import hikari
from hikari import embeds

PREMIUM_PERKS = "\n".join([
    f"- More role bindings allowed (from {LIMITS['BINDS']['FREE']} to {LIMITS['BINDS']['PREMIUM']}).",
    "Able to verify/update all members in your server (`/verifyall`).",
    "Able to add a verification button to your `/verifychannel` and customize the text.",
    f"- Access to the `Pro` version of Bloxlink - a bot in less servers, so downtime is very minimal.",
    "- Customize the name of Magic Roles.",
    "- No cooldown on some commands.",
    "- More restrictions (`/restrict`) " + f"allowed (from {LIMITS['RESTRICTIONS']['FREE']} to {LIMITS['RESTRICTIONS']['PREMIUM']}).",
    "- And more!"
])

@Bloxlink.command
class DonateCommand(Bloxlink.Module):
    """Learn how to receive Bloxlink Premium"""

    def __init__(self):
        self.aliases = ["premium"]
        self.dm_allowed = True
        self.slash_enabled = True

    async def __main__(self, ctx: Bloxlink.Context) -> None:
        guild_id = ctx.guild_id

        embed = embeds.Embed(
            title="Bloxlink Premium",
            description="Premium purchases help support Bloxlink!",
            color=hikari.Color.from_rgb(57, 152, 214)
        )

        embed.add_field(
            name="Server Premium",
            value="Unlocks premium commands, lessens restrictions, no ads for your server verification page, and more for your server.",
            inline=False
        )

        view = hikari.build_action_row(
            hikari.LinkButton(
                label="Click for Server Premium",
                url=f"https://blox.link/dashboard/guilds/{guild_id}/premium"
            )
        )

        await ctx.respond(embed=embed, component=view)
