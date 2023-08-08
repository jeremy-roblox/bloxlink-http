from hikari import Embed

from resources.bloxlink import instance as bloxlink
from resources.models import CommandContext, PremiumModel
from resources.premium import get_premium_status


@bloxlink.command(category="Miscellaneous")
class StatusCommand:
    """view your premium status"""

    async def __main__(self, ctx: CommandContext):
        premium_status: PremiumModel = await get_premium_status(guild_id=ctx.guild_id)
        embed = Embed()

        if premium_status.active:
            embed.description = ":heart: Thanks for being a **premium subscriber!**"
            embed.color = 0xFDC333
            embed.add_field(name="Premium Status", value="Active", inline=True)
            embed.add_field(name="Tier", value=premium_status.tier, inline=True)
            embed.add_field(name="Payment Source", value=premium_status.charge_source, inline=True)
            embed.add_field(name="Unlocked Features", value=str(premium_status), inline=True)
        else:
            embed.description = (
                "This server does not have premium. A server admin may purchase it [here](https://blox.link)."
            )

        await ctx.response.send(embed=embed)
