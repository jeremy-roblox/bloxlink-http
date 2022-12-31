from resources.bloxlink import instance as bloxlink
from resources.groups import get_group
from resources.models import CommandContext
from resources.component_helper import check_all_modified, set_custom_id_data
from hikari.commands import CommandOption, OptionType
import hikari


async def bind_menu_select_roleset(interaction: hikari.ComponentInteraction):
    await set_custom_id_data(interaction.message,
                            "bind_menu:select_menu:add_role:roleset_menu",
                            6,
                            interaction.values)

    return interaction.build_deferred_response(hikari.interactions.base_interactions.ResponseType.DEFERRED_MESSAGE_UPDATE)

async def bind_menu_select_role(interaction: hikari.ComponentInteraction):
    await set_custom_id_data(interaction.message,
                             "bind_menu:select_menu:add_role:role_menu",
                             6,
                             interaction.values)

    return interaction.build_deferred_response(hikari.interactions.base_interactions.ResponseType.DEFERRED_MESSAGE_UPDATE)

async def bind_menu_select_criteria(interaction: hikari.ComponentInteraction):
    message = interaction.message

    await set_custom_id_data(message,
                             "bind_menu:select_menu:add_role:criteria_menu",
                             6,
                             interaction.values)

    all_modified = await check_all_modified(
        message,
        "bind_menu:select_menu:add_role:criteria_menu",
        "bind_menu:select_menu:add_role:role_menu",
        "bind_menu:select_menu:add_role:roleset_menu"
    )

    if all_modified:
        # add to initial embed
        initial_message = await interaction.fetch_message()
        # get custom id segment
        # get message


    return interaction.build_deferred_response(hikari.interactions.base_interactions.ResponseType.DEFERRED_MESSAGE_UPDATE)


async def bind_menu_add_role_button(interaction: hikari.ComponentInteraction):
    custom_id = interaction.custom_id

    channel_id = interaction.channel_id
    guild_id   = interaction.guild_id

    member  = interaction.member
    message = interaction.message

    guild = await interaction.fetch_guild()

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
        bloxlink.rest.build_action_row().add_select_menu(f"bind_menu:select_menu:add_role:roleset_menu:{message.id}")
        .set_placeholder("Bind this Group rank")
    )

    for roleset_name, roleset_value in group.rolesets.items():
        if len(roleset_menu.options) < 25:
            roleset_menu = roleset_menu.add_option(roleset_name, str(roleset_value)).add_to_menu()

    roleset_menu = roleset_menu.add_to_container()

    role_menu = (
        bloxlink.rest.build_action_row().add_select_menu(f"bind_menu:select_menu:add_role:role_menu:{message.id}")
        .set_placeholder("..to this Discord role")
    )

    for role_id, role in guild.roles.items():
        if role.name != "@everyone" and len(role_menu.options) < 25:
            role_menu = role_menu.add_option(role.name, str(role_id)).add_to_menu()

    role_menu = role_menu.add_to_container()


    criteria_menu = (
        bloxlink.rest.build_action_row().add_select_menu(f"bind_menu:select_menu:add_role:criteria_menu:{message.id}")
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
        "bind_menu:select_menu:add_role:roleset_menu": bind_menu_select_roleset,
        "bind_menu:select_menu:add_role:role_menu": bind_menu_select_role,
        "bind_menu:select_menu:add_role:criteria_menu": bind_menu_select_criteria
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
                .add_button(hikari.ButtonStyle.PRIMARY, f"bind_menu:add_roles:{group_id}:null")
                    .set_label("Bind new role")
                    .add_to_container()
                .add_button(hikari.ButtonStyle.PRIMARY, "bind_menu:finish")
                    .set_label("Save changes")
                    .add_to_container()
            )

            await ctx.response.send(embed=embed, components=button_menu)

            # We're done here. Button clicks invoke above functions
