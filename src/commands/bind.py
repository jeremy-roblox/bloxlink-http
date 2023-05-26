from resources.bloxlink import instance as bloxlink
from resources.groups import get_group
from resources.binds import count_binds, get_bind_desc, create_bind
from resources.models import CommandContext
from resources.component_helper import (
    check_all_modified,
    set_custom_id_data,
    set_components,
    get_custom_id_data,
)
from hikari.commands import CommandOption, OptionType
import hikari


async def bind_menu_select_criteria(interaction: hikari.ComponentInteraction):
    message = interaction.message

    # depending on choice, show more select menus to message
    bind_choice = interaction.values[0]

    show_roleset_menu = False
    show_discord_role_menu = False

    original_message_id = get_custom_id_data(interaction.custom_id, 3)
    group_id = get_custom_id_data(interaction.custom_id, 4)

    if bind_choice in ("exact_rank"):
        show_roleset_menu = True

    print("select_criteria", interaction.custom_id)

    if show_roleset_menu:
        group = await get_group(group_id)

        roleset_menu = bloxlink.rest.build_message_action_row().add_text_menu(
            f"bind:select_roleset:{original_message_id}:{bind_choice}",
            placeholder="Bind this Group rank",
        )

        for roleset_value, roleset_name in group.rolesets.items():
            if roleset_name != "Guest" and len(roleset_menu.options) < 25:
                roleset_menu.add_option(roleset_name, f"{roleset_name}BLOXLINK_SPLIT{str(roleset_value)}")

        message.embeds[0].description = (
            "Very good! Now, choose the roleset from your group " "that should receive the role."
        )

        await set_components(message, components=[roleset_menu.parent])

    return interaction.build_deferred_response(
        hikari.interactions.base_interactions.ResponseType.DEFERRED_MESSAGE_UPDATE
    )


async def bind_menu_select_roleset(interaction: hikari.ComponentInteraction):
    message = interaction.message
    roleset_choice = interaction.values[0]

    guild = await interaction.fetch_guild()

    print("select_roleset", interaction.custom_id)

    original_message_id = get_custom_id_data(interaction.custom_id, 3)
    bind_choice = get_custom_id_data(interaction.custom_id, 4)
    print("here", original_message_id)

    # show discord role menu
    role_menu = (
        bloxlink.rest.build_message_action_row()
        .add_text_menu(f"bind:select_role:{original_message_id}:{roleset_choice}:{bind_choice}")
        .set_placeholder("Attach this Discord role to the Group Roleset")
    )

    for role_id, role in guild.roles.items():
        if role.name != "@everyone" and len(role_menu.options) < 25:
            role_menu.add_option(role.name, f"{role.name}BLOXLINK_SPLIT{str(role_id)}")

    message.embeds[0].description = (
        "Finally, choose the role from your "
        "server that you want members to receive "
        "who qualify for the bind.\nNo existing role? "
        "No problem! Click the 'Create Role' button above!"
    )

    original_message_id = get_custom_id_data(interaction.id, 5)

    await set_components(message, components=[role_menu.parent])

    return interaction.build_deferred_response(
        hikari.interactions.base_interactions.ResponseType.DEFERRED_MESSAGE_UPDATE
    )


async def bind_menu_select_role(interaction: hikari.ComponentInteraction):
    message = interaction.message
    role_data = interaction.values[0].split("BLOXLINK_SPLIT")

    role_name, role_id = role_data[0], role_data[1]

    print("select_role", interaction.custom_id)

    original_message_id = get_custom_id_data(interaction.custom_id, 3)
    roleset_data = get_custom_id_data(interaction.custom_id, 4)
    bind_choice = get_custom_id_data(interaction.custom_id, 5)

    channel = await interaction.fetch_channel()
    original_message = await channel.fetch_message(original_message_id)

    # roleset_name, roleset_id = roleset_data.split('BLOXLINK_SPLIT')[0], roleset_name.split('BLOXLINK_SPLIT')[1]

    new_description = original_message.embeds[0].description.split("\n")

    if "Pending changes:" not in new_description:
        new_description.append("Pending changes:")

    new_description.append(
        f"_People with roleset **{roleset_data.split('BLOXLINK_SPLIT')[0]}** will receive role <@&{role_id}>_"
    )

    new_embed = hikari.Embed(title="New Group Bind [UNSAVED CHANGES]", description="\n".join(new_description))

    original_message.embeds[0] = new_embed

    await original_message.edit(embed=new_embed)
    await message.delete()

    existing_role_ids = get_custom_id_data("bind_menu:save_button", 5, original_message)

    await set_custom_id(
        original_message,
        "bind_menu:save_button",
        f"{bind_choice}-{original_message}-{([role_id] + [existing_role_ids]) if existing_role_ids else [role_id]}",
    )

    # await set_custom_id_data(original_message, "bind_menu:save_button", 4, bind_choice)

    # existing_role_ids = get_custom_id_data("bind_menu:save_button", 5, original_message)

    # await set_custom_id_data(original_message, "bind_menu:save_button", 5, ([role_id] + [existing_role_ids]) if existing_role_ids else [role_id])

    return interaction.build_response(
        hikari.interactions.base_interactions.ResponseType.MESSAGE_CREATE
    ).set_content(
        f"Bind added to your in-progress workflow! [Click here](https://discord.com/channels/{interaction.guild_id}/{interaction.channel_id}/{original_message_id})"
        " and click the Save button to save the bind to your server!"
    )

    # await interaction.edit_initial_response(
    #     f"Bind added to your in-progress workflow! [Click here](https://discord.com/channels/{interaction.guild_id}/{interaction.channel_id}/{original_message_id})"
    #     " and click the Save button to save the bind to your server!")


async def bind_menu_add_role_button(interaction: hikari.ComponentInteraction):
    custom_id = interaction.custom_id

    channel_id = interaction.channel_id
    guild_id = interaction.guild_id

    member = interaction.member
    message = interaction.message

    guild = await interaction.fetch_guild()

    await interaction.create_initial_response(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)

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
        title="Binding Role Interactive Wizard",
        description=(
            "This menu will let you connect a Group rank to a "
            "Discord role.\nPlease choose the criteria for this bind."
        ),
    )

    # roleset_menu = (
    #     bloxlink.rest.build_message_action_row().add_select_menu(f"bind_menu:select_menu:add_role:roleset_menu:{message.id}")
    #     .set_placeholder("Bind this Group rank")
    # )

    # for roleset_value, roleset_name in group.rolesets.items():
    #     if len(roleset_menu.options) < 25:
    #         roleset_menu = roleset_menu.add_option(roleset_name, str(roleset_value)).add_to_menu()

    # roleset_menu = roleset_menu.add_to_container()

    # role_menu = (
    #     bloxlink.rest.build_message_action_row().add_select_menu(f"bind_menu:select_menu:add_role:role_menu:{message.id}")
    #     .set_placeholder("..to this Discord role")
    # )

    # for role_id, role in guild.roles.items():
    #     if role.name != "@everyone" and len(role_menu.options) < 25:
    #         role_menu = role_menu.add_option(role.name, str(role_id)).add_to_menu()

    # role_menu = role_menu.add_to_container()

    criteria_menu = (
        bloxlink.rest.build_message_action_row()
        .add_text_menu(f"bind:select_criteria:{message.id}:{group_id}")
        .set_placeholder("Choose condition")
        .add_option("Rank must match exactly...", "exact_rank")
        .add_option("Rank must be greater than or equal to...", "gte")
        .add_option("Rank must be less than or equal to...", "lte")
        .add_option("Rank must be within 2 rolesets...", "within")
        .add_option("User must NOT be a member of this group", "guest_role")
    )

    await interaction.execute(embed=embed, components=[criteria_menu.parent])


async def bind_menu_save_button(interaction: hikari.ComponentInteraction):
    message = interaction.message
    guild_id = interaction.guild_id
    # print(await interaction.fetch_initial_response())
    # print(await interaction.fetch_parent_message())

    print(interaction.custom_id)
    # print(message.content)
    # print(message.make_link(interaction.guild_id))

    # print(await get_custom_id_data(""))

    group_id = get_custom_id_data(interaction.custom_id, 3)
    bind_mode = get_custom_id_data(interaction.custom_id, 4)
    role_ids = get_custom_id_data(interaction.custom_id, 5)

    print(role_ids)

    if bind_mode == "exact_rank":
        await create_bind(
            guild_id,
            bind_type="group",
            bind_id=group_id,
            roles=role_ids.split(","),
            # roleset=
        )

    return interaction.build_response(
        hikari.interactions.base_interactions.ResponseType.MESSAGE_CREATE
    ).set_content("Saved your binds")


@bloxlink.command(
    category="Administration",
    defer=True,
    permissions=hikari.Permissions.MANAGE_GUILD,
    accepted_custom_ids={
        "bind_menu:add_roles_button": bind_menu_add_role_button,
        "bind:select_roleset": bind_menu_select_roleset,
        "bind:select_role": bind_menu_select_role,
        "bind:select_criteria": bind_menu_select_criteria,
        "bind_menu:save_button": bind_menu_save_button,
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
                        name="Bind all current and future group roles", value="entire_group"
                    ),
                    hikari.CommandChoice(name="Choose specific group roles", value="specific_roles"),
                ],
                is_required=True,
            ),
        ]
    )
    async def group(self, ctx: CommandContext):
        """bind a group to your server"""

        group_id = ctx.options["group_id"]
        bind_mode = ctx.options["bind_mode"]

        group = await get_group(group_id)

        bind_count = await count_binds(ctx.guild_id, group.id)

        if bind_mode == "specific_roles":
            embed = hikari.Embed(
                title="New Group Bind",
                description="No binds exist for this group! Click the button below to create your first bind."
                if bind_count == 0
                else await get_bind_desc(ctx.guild_id, group.id),
            )

            button_menu = (
                bloxlink.rest.build_message_action_row()
                .add_interactive_button(
                    hikari.ButtonStyle.PRIMARY,
                    f"bind_menu:add_roles_button:{group_id}",
                    label="Bind new role",
                )
                .add_interactive_button(
                    hikari.ButtonStyle.SUCCESS,
                    f"bind_menu:save_button:{group_id}",
                    label="Save changes",
                )
            )

            await ctx.response.send(embed=embed, components=button_menu)

            # We're done here. Button clicks invoke above functions
