from resources.bloxlink import instance as bloxlink
from resources.groups import get_group
from resources.models import CommandContext
from hikari.commands import CommandOption, OptionType
from hikari import ButtonStyle
import hikari


async def bind_menu_select_roleset(interaction: hikari.ComponentInteraction):
    custom_id = interaction.custom_id

    message = interaction.message

    for action_row in message.components:
        for component in action_row.components:
            if component.custom_id.startswith("bind_menu:select_menu:add_role:roleset_menu"):
                custom_id_data = component.custom_id.split(":")
                selected_rolesets = (custom_id_data[3] if len(custom_id_data) >= 4 else "").split(",")

                for roleset_value in interaction.values:
                    selected_rolesets.append(roleset_value)

                custom_id_data[3] = ",".join(selected_rolesets)
                component.custom_id = ":".join(custom_id_data)

                await message.edit(components=[a.components])

                print(f"edited with new custom id {component.custom_id}")

                break


    return interaction.create_initial_response(hikari.MESSAGE_UPDATE)

async def bind_menu_add_role_button(interaction: hikari.ComponentInteraction):
    custom_id = interaction.custom_id

    channel_id = interaction.channel_id
    guild_id   = interaction.guild_id

    member  = interaction.member
    message = interaction.message

    await interaction.create_initial_response(
        hikari.ResponseType.DEFERRED_MESSAGE_CREATE
    )

    custom_id_data = custom_id.split(":")

    group_id = custom_id_data[2] if len(custom_id_data) >= 3 else None

    if not group_id:
        return

    group = await get_group(group_id)

    # print(group)

    # embed = message.embeds[0]

    # custom_id_data = custom_id.split(":")

    # role_data = (custom_id_data[2] if len(custom_id_data) >= 3 else "").split(",")


    # await message.edit(embed=embed)


    embed = hikari.Embed(
        title="Binding Role",
        description=("This menu will let you connect a Group rank to a "
                     "Discord role. Please choose the group rank "
                     "and Discord role below.")
    )

    roleset_menu = (
        bloxlink.rest.build_action_row().add_select_menu("bind_menu:select_menu:add_role:roleset_menu")
        .set_placeholder("Bind this Group rank")
    )

    for roleset_name, roleset_value in group.rolesets.items():
        roleset_menu = roleset_menu.add_option(roleset_name, str(roleset_value)).add_to_menu()

    roleset_menu = roleset_menu.add_to_container()

    role_menu = (
        bloxlink.rest.build_action_row().add_select_menu("bind_menu:select_menu:add_role:role_menu")
        .set_placeholder("..to this Discord role")
        .add_option("test", "test")
            .add_to_menu()
        .add_to_container()
    )

    criteria_menu = (
        bloxlink.rest.build_action_row().add_select_menu("bind_menu:select_menu:add_role:criteria_menu")
        .set_placeholder("..that meet this condition")
        .add_option("Rank must match exactly", "bind_menu:select_menu:add_role:exact_rank")
            .add_to_menu()
        .add_option("Rank must be greater than or equal to", "bind_menu:select_menu:add_role:gte")
            .add_to_menu()
        .add_option("Rank must be less than or equal to", "bind_menu:select_menu:add_role:lte")
            .add_to_menu()
        .add_to_container()
    )


    await interaction.execute(embed=embed, components=[roleset_menu, role_menu, criteria_menu])



@bloxlink.command(
    category="Administration",
    defer=True,
    permissions=hikari.Permissions.MANAGE_GUILD,

    accepted_custom_ids = {
        "bind_menu:add_roles": bind_menu_add_role_button,
        "bind_menu:select_menu:add_role:roleset_menu": bind_menu_select_roleset
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
                .add_button(ButtonStyle.PRIMARY, f"bind_menu:add_roles:{group_id}:null")
                    .set_label("Add roles")
                    .add_to_container()
                .add_button(ButtonStyle.PRIMARY, "bind_menu:finish")
                    .set_label("Finish")
                    .add_to_container()
            )

            await ctx.response.send(embed=embed, components=button_menu)

            # We're done here. Button clicks invoke above functions
