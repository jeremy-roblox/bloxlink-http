from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext
import resources.binds as binds
import resources.roblox.users as users
import hikari

async def verify_button_click(ctx: CommandContext):
    yield await ctx.response.defer(True)

    roblox_account = await users.get_user_account(ctx.user, raise_errors=False)
    message_response = await binds.apply_binds(
        ctx.member, ctx.guild_id, roblox_account, moderate_user=True
    )

    await ctx.response.send(embed=message_response.embed, components=message_response.components)


@bloxlink.command(
    category="Administration",
    permissions=hikari.Permissions.MANAGE_GUILD,
    defer=True,
    defer_with_ephemeral=True,
    accepted_custom_ids={
        "verify_view:verify_button": verify_button_click,
    }
)
class VerifyChannelCommand:
    """post a message that users can interact with to get their roles"""

    async def __main__(self, ctx: CommandContext):
        guild: hikari.RESTGuild = await bloxlink.rest.fetch_guild(ctx.guild_id)

        action_row = bloxlink.rest.build_message_action_row()
        action_row.add_interactive_button(
            hikari.ButtonStyle.SUCCESS,
            "verify_view:verify_button",
            label="Verify with Bloxlink",
            # emoji="<:chain:970894927196209223>"
        )
        action_row.add_link_button(
            "https://www.youtube.com/playlist?list=PLz7SOP-guESE1V6ywCCLc1IQWiLURSvBE",
            label="Need help?",
            emoji="❔"
        )

        message = await ctx.response.send(
            f"Welcome to **{guild.name}!** Click the button below to Verify with Bloxlink and gain access to the rest of the server.",
            components=[action_row],
            channel=await ctx.interaction.fetch_channel()
        )

        await ctx.response.send("Posted!", ephemeral=True)
