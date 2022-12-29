from resources.bloxlink import instance as bloxlink
from resources.groups import get_group
from resources.models import CommandContext
from hikari.commands import CommandOption, OptionType
from hikari import ButtonStyle
import hikari


async def bind_menu_add_role_button(interaction: hikari.ComponentInteraction):
    print("got add button click")


@bloxlink.command(
    category="Administration",
    defer=True,
    permissions=hikari.Permissions.MANAGE_GUILD,

    accepted_custom_ids = {
        "bind_menu:add_roles": bind_menu_add_role_button
    },
)
class BindCommand:
    """bind Discord role(s) to Roblox entities"""

    @bloxlink.subcommand(
        options=[
            CommandOption(
                type=OptionType.INTEGER,
                name="group_id",
                description="What is your group ID?",
                is_required=True,
            ),
            CommandOption(
                type=OptionType.STRING,
                name="bind_mode",
                description="How should we merge your group with Discord?",
                choices=[
                    hikari.CommandChoice(
                        name="Bind all current and future group roles", value="entire_group"),
                    hikari.CommandChoice(
                        name="Choose specific group roles", value="specific_roles")
                ],
                is_required=True
            )
        ]
    )
    async def group(self, ctx: CommandContext):
        """bind a group to your server"""

        group_id  = ctx.options["group_id"]
        bind_mode = ctx.options["bind_mode"]

        group = await get_group(group_id)

        if bind_mode == "specific_roles":
            embed = hikari.Embed(
                title="New Group Bind"
            )

            button_menu = (
                bloxlink.rest.build_action_row()
                .add_button(ButtonStyle.PRIMARY, "bind_menu:add_roles")
                    .set_label("Add roles")
                    .add_to_container()
                .add_button(ButtonStyle.PRIMARY, "bind_menu:finish")
                    .set_label("Finish")
                    .add_to_container()
            )

            await ctx.response.send(embed=embed, components=button_menu)

            # We're done here. Button clicks invoke above functions
