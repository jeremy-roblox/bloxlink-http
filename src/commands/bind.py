from resources.bloxlink import instance as bloxlink
from resources.exceptions import RobloxNotFound
from resources.assets import get_asset
from resources.badges import get_badge
from resources.gamepasses import get_gamepass
from resources.groups import get_group
from resources.binds import count_binds, get_bind_desc, create_bind
from resources.models import CommandContext
from resources.component_helper import (
    check_all_modified,
    set_custom_id_data,
    set_components,
    get_custom_id_data,
)
from resources.constants import SPLIT_CHAR, GROUP_RANK_CRITERIA, GROUP_RANK_CRITERIA_TEXT
from resources.prompts import (
    build_role_selection_prompt,
    build_roleset_selection_prompt,
    build_group_criteria_prompt,
    build_interactive_bind_base,
)
from hikari.commands import CommandOption, OptionType
import hikari
import re

DISCORD_ID_REGEX = r"(\d{17,})"


async def bind_menu_select_criteria(interaction: hikari.ComponentInteraction):
    """
    Handles the group bind criteria selection response & sets up the next prompt accordingly.

    Sets up the group rank selection prompt for all criteria except "all" and "gst", those two
    will be directed straight to role selection.
    """

    message = interaction.message

    # depending on choice, show more select menus to message
    bind_choice = interaction.values[0]

    show_roleset_menu: bool = bind_choice in ("equ", "gte", "lte", "rng")

    original_message_id, group_id = get_custom_id_data(interaction.custom_id, segment_min=3, segment_max=4)

    print("select_criteria", interaction.custom_id)
    prompt = None

    if show_roleset_menu:
        value_count = 1 if bind_choice != "rng" else 2
        prompt = await build_roleset_selection_prompt(
            f"{original_message_id}:{bind_choice}",
            group_id,
            min_values=value_count,
            max_values=value_count,
            embed=message.embeds[0],
        )
    else:
        # Skip to the role selection prompt.
        # custom_id has double colons because that is where a roleset would go (segment 4).
        prompt = await build_role_selection_prompt(
            f"{original_message_id}::{bind_choice}", interaction.guild_id, embed=message.embeds[0]
        )

    if prompt:
        message.embeds[0] = prompt.embed
        await set_components(message, components=prompt.components)

    return interaction.build_deferred_response(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)


async def bind_menu_select_roleset(interaction: hikari.ComponentInteraction):
    """
    Handles the selected group rank response, one or two depending on the bind condition.
    Sets up role-selection prompt.
    """
    message = interaction.message
    roleset_choices = interaction.values

    print("select_roleset", interaction.custom_id)

    original_message_id = get_custom_id_data(interaction.custom_id, 3)
    bind_choice = get_custom_id_data(interaction.custom_id, 4)
    # print("here", original_message_id)

    # show discord role menu
    roleset_str = (
        f"{roleset_choices[0]}{f'{SPLIT_CHAR}{roleset_choices[1]}' if len(roleset_choices) > 1 else ''}"
    )
    prompt = await build_role_selection_prompt(
        f"{original_message_id}:{roleset_str}:{bind_choice}",
        interaction.guild_id,
        embed=message.embeds[0],
    )

    message.embeds[0] = prompt.embed
    await set_components(message, components=prompt.components)

    return interaction.build_deferred_response(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)


async def bind_menu_select_role(interaction: hikari.ComponentInteraction):
    """
    Handles the role selection prompt response.

    Saves the values from the prior steps (passed via the component custom_id) and
    the selections from this prompt to the original embed description.
    It then sets up the select roles to remove prompt.
    """
    message = interaction.message

    print("inter vals", interaction.values)
    role_data = {}
    for item in interaction.values:
        item_data = item.split(SPLIT_CHAR)
        role_data[item_data[1]] = item_data[0]

    print("select_role", interaction.custom_id)

    custom_data = get_custom_id_data(interaction.custom_id, segment_min=3, segment_max=5)
    original_message_id = custom_data[0]

    is_group_bind = True

    # Depending on user choices, this segment will either be roleset data or the bind type. Determine that here.
    roleset_data = custom_data[1]
    if SPLIT_CHAR in roleset_data:
        roleset_data = roleset_data.split(SPLIT_CHAR)
    elif roleset_data in ("asset", "badge", "gamepass"):
        is_group_bind = False

    # Final segment only exists if this is a group bind.
    if is_group_bind:
        bind_choice = custom_data[2]

    channel = await interaction.fetch_channel()
    original_message = await channel.fetch_message(original_message_id)

    # Save current configuration to the right field.
    # Start by getting the field and then build the updated field value.
    new_description = original_message.embeds[0].fields[1].value.split("\n")

    default_field_str = "*The binds you're making will be added here!*"
    if default_field_str in new_description:
        new_description.remove(default_field_str)

    if "Pending changes:" not in new_description:
        new_description.append("Pending changes:")

    # Generate the bind string for the field.
    prefix = ""
    content = ""
    role_mention_str = ", ".join(f"<@&{val}>" for val in role_data.keys())

    if is_group_bind:
        prefix = GROUP_RANK_CRITERIA_TEXT.get(bind_choice, "[ERROR] No matching criteria.")
        content = ""
        if bind_choice in ("equ", "gte", "lte"):
            content = roleset_data
        elif bind_choice in ("gst", "all"):
            content = "<GROUP ID> (TBD)"
        elif bind_choice == "rng":
            min_rank = roleset_data[0]
            max_rank = roleset_data[1]

            content = f"{min_rank}** and **{max_rank}"
    else:
        prefix = "People who own"
        content = f"this {roleset_data}"

    # Check for duplicates in the field & update accordingly. Removes old entry and appends again
    role_list = role_data.keys()
    for item in new_description:
        if item[3:].startswith(f"{prefix} **{content}**"):
            original_roles = []

            # Only get roles to be given, we'll just discard the roles to remove if an entry is there.
            # User can add them back in the next step
            if "these roles removed:" in item:
                split_item = item.split("these roles removed")
                original_roles = re.findall(DISCORD_ID_REGEX, split_item[0])

            role_list = list(set(role_list).union(set(original_roles)))

            new_description.remove(item)
            break

    role_mention_str = ", ".join(f"<@&{val}>" for val in role_list)
    new_bind_str = (
        f"- _{prefix} **{content}** will receive "
        f"role{'s' if len(role_data.keys()) > 1  else ''} {role_mention_str}_"
    )
    new_description.append(new_bind_str)

    # Update title if necessary
    original_title = original_message.embeds[0].title
    new_title = (
        original_title if "[UNSAVED CHANGES]" in original_title else f"{original_title} [UNSAVED CHANGES]"
    )

    # Update the embed with the new bindings made.
    new_embed = original_message.embeds[0]
    new_embed.title = new_title
    new_embed.fields[1].value = "\n".join(new_description)

    # Save to the original message
    await original_message.edit(embed=new_embed)

    # Setup remove role prompt
    prompt = await build_role_selection_prompt(
        custom_id=original_message_id,
        guild_id=interaction.guild_id,
        placeholder="Choose which role(s) will be removed from people who apply to this bind.",
        include_none=True,
        remove_text=True,
        embed=message.embeds[0],
    )

    message.embeds[0] = prompt.embed
    await set_components(message, components=prompt.components)

    return interaction.build_deferred_response(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)


async def bind_menu_select_remove_roles(interaction: hikari.ComponentInteraction):
    """
    Handles the response from the selection prompt asking if users want roles to be removed.
    """
    original_message_id = get_custom_id_data(interaction.custom_id, segment=3)

    skip_bool = False
    for item in interaction.values:
        if "None" in item:
            skip_bool = True
            break

    if not skip_bool:
        channel = await interaction.fetch_channel()
        original_message = await channel.fetch_message(original_message_id)
        original_embed = original_message.embeds[0]

        original_desc_list = original_embed.fields[1].value.splitlines()
        last_item = original_desc_list[-1]

        role_data = {}
        for item in interaction.values:
            item_data = item.split(SPLIT_CHAR)
            role_data[item_data[1]] = item_data[0]
        role_mention_str = ", ".join(f"<@&{val}>" for val in role_data.keys())

        last_item = last_item[:-1] + f", and will have these roles removed: {role_mention_str}_"
        original_desc_list[-1] = last_item

        description = "\n".join(original_desc_list)
        original_embed.fields[1].value = description

        await original_message.edit(embed=original_embed)

    await interaction.message.delete()
    return (
        interaction.build_response(hikari.interactions.base_interactions.ResponseType.MESSAGE_CREATE)
        .set_content(
            f"Bind added to your in-progress workflow! [Click here](https://discord.com/channels/{interaction.guild_id}/{interaction.channel_id}/{original_message_id})"
            " and click the Save button to save the bind to your server!"
        )
        .set_flags(hikari.MessageFlag.EPHEMERAL)
    )


async def bind_menu_add_role_button(interaction: hikari.ComponentInteraction):
    """
    Handles what will occur on the add role button press.

    Depending on the bind type, this will do different things, will only be
    applicable for group binds where specific ranks are desired, as well as
    asset, badge, and gamepass bindings.
    """
    custom_id = interaction.custom_id
    message = interaction.message

    await interaction.create_initial_response(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)

    bind_type, bind_id = get_custom_id_data(custom_id, segment_min=3, segment_max=4)

    embed = hikari.Embed(
        title="Binding Role Interactive Wizard",
    )

    prompt = None

    if bind_type == "group":
        if not bind_id:
            return

        group = await get_group(bind_id)

        prompt = build_group_criteria_prompt(f"{message.id}:{bind_id}", embed=embed)

    elif bind_type in ("asset", "badge", "gamepass"):
        # Direct the user straight to the role selection prompt.
        prompt = await build_role_selection_prompt(
            f"{message.id}:{bind_type}", interaction.guild_id, embed=embed
        )

    else:
        raise NotImplementedError(f"The bind type {bind_type} is not handled yet!")

    if prompt:
        await interaction.execute(embed=prompt.embed, components=prompt.components)


async def bind_menu_save_button(interaction: hikari.ComponentInteraction):
    """
    Saves the configuration found in the description of the embed to the database.
    """
    message = interaction.message
    guild_id = interaction.guild_id

    embed = message.embeds[0]
    new_binds_field = embed.fields[1]
    bindings = new_binds_field.value.splitlines()[1:]

    bind_type, prompt_id = get_custom_id_data(interaction.custom_id, segment_min=3, segment_max=4)

    if len(bindings) == 0:
        return (
            interaction.build_response(hikari.interactions.base_interactions.ResponseType.MESSAGE_CREATE)
            .set_content("You have no new bindings to save!")
            .set_flags(hikari.MessageFlag.EPHEMERAL)
        )

    for bind in bindings:
        # remove underscores and bulletpoint
        bind = bind[3:-1]

        # Get all role IDs, need to rework if adding roles to remove.
        # Probably will split on the text "roles to remove" if it exists first.

        role_ids = []
        remove_role_ids = []

        remove_split_str = ", and will have these roles removed:"
        if remove_split_str in bind:
            remove_split = bind.split(remove_split_str)

            role_ids = re.findall(DISCORD_ID_REGEX, remove_split[0])
            remove_role_ids = re.findall(DISCORD_ID_REGEX, remove_split[1])
        else:
            role_ids = re.findall(DISCORD_ID_REGEX, bind)

        # Get all matches in-between double asterisks
        named_ranks = re.findall(r"\*\*(.*?)\*\*", bind)

        if bind_type == "group":
            group_bind_type = ""

            # Determine the type of binding based on the text desc.
            for criteria_type, criteria_vals in GROUP_RANK_CRITERIA_TEXT.items():
                if criteria_vals in bind:
                    group_bind_type = criteria_type
                    break

            group_data = await get_group(prompt_id)
            group_rolesets = group_data.rolesets.items()

            rank_ids = []
            for rank in named_ranks:
                for k, v in group_rolesets:
                    if v == rank:
                        rank_ids.append(k)

            if group_bind_type == "equ":
                await create_bind(
                    guild_id,
                    bind_type,
                    bind_id=int(prompt_id),
                    roles=role_ids,
                    remove_roles=remove_role_ids,
                    roleset=rank_ids[0],
                )

            elif group_bind_type == "gte":
                # TODO: Consider changing so only "min" option is set.
                await create_bind(
                    guild_id,
                    bind_type,
                    bind_id=int(prompt_id),
                    roles=role_ids,
                    remove_roles=remove_role_ids,
                    roleset=-abs(rank_ids[0]),
                )

            elif group_bind_type == "lte":
                await create_bind(
                    guild_id,
                    bind_type,
                    bind_id=int(prompt_id),
                    roles=role_ids,
                    remove_roles=remove_role_ids,
                    max=rank_ids[0],
                )

            elif group_bind_type == "rng":
                await create_bind(
                    guild_id,
                    bind_type,
                    bind_id=int(prompt_id),
                    roles=role_ids,
                    remove_roles=remove_role_ids,
                    min=rank_ids[0],
                    max=rank_ids[1],
                )

            elif group_bind_type == "gst":
                await create_bind(
                    guild_id,
                    bind_type,
                    bind_id=int(prompt_id),
                    roles=role_ids,
                    remove_roles=remove_role_ids,
                    guest=True,
                )

            elif group_bind_type == "all":
                await create_bind(
                    guild_id,
                    bind_type,
                    bind_id=int(prompt_id),
                    roles=role_ids,
                    remove_roles=remove_role_ids,
                    everyone=True,
                )

            else:
                raise NotImplementedError(f"No matching group bind type was found. - Bind string: {bind}")

        elif bind_type in ("asset", "badge", "gamepass"):
            raise NotImplementedError("Alternative bind type found.")

    prompt = await build_interactive_bind_base(bind_type, prompt_id, interaction.guild_id)
    await message.edit(embed=prompt.embed)

    return (
        interaction.build_response(hikari.interactions.base_interactions.ResponseType.MESSAGE_CREATE)
        .set_content("Saved your binds")
        .set_flags(hikari.MessageFlag.EPHEMERAL)
    )


@bloxlink.command(
    category="Administration",
    defer=True,
    permissions=hikari.Permissions.MANAGE_GUILD,
    accepted_custom_ids={
        "bind_menu:add_roles_button": bind_menu_add_role_button,
        "bind:sel_crit": bind_menu_select_criteria,
        "bind:sel_rank": bind_menu_select_roleset,
        "bind:sel_role": bind_menu_select_role,
        "bind:sel_rmv_role": bind_menu_select_remove_roles,
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
        """Bind a group to your server"""

        group_id = ctx.options["group_id"]
        bind_mode = ctx.options["bind_mode"]

        try:
            group = await get_group(group_id)
        except RobloxNotFound:
            # Can't be ephemeral sadly bc of the defer state for the command.
            await ctx.response.send(
                f"The group ID ({group_id}) you gave is either invalid or does not exist."
            )
            return

        if bind_mode == "specific_roles":
            prompt = await build_interactive_bind_base("group", group_id, ctx.guild_id)

            await ctx.response.send(embed=prompt.embed, components=prompt.components)

        elif bind_mode == "entire_group":
            # Isn't interactive - just makes the binding and tells the user if it worked or not.
            response = f'Your group binding for group "{group.name}" ({group_id}) has been saved.'
            try:
                await create_bind(ctx.guild_id, bind_type="group", bind_id=group_id)
            except NotImplementedError:
                response = f'You already have a group binding for group "{group.name}" ({group_id}). No changes were made.'

            await ctx.response.send(response)

    @bloxlink.subcommand(
        options=[
            CommandOption(
                type=OptionType.INTEGER,
                name="asset_id",
                description="What is your asset ID?",
                is_required=True,
            )
        ]
    )
    async def asset(self, ctx: CommandContext):
        """Bind an asset to your server"""

        asset_id = ctx.options["asset_id"]

        try:
            await get_asset(asset_id)
        except RobloxNotFound:
            # Can't be ephemeral sadly bc of the defer state for the command.
            await ctx.response.send(
                f"The asset ID ({asset_id}) you gave is either invalid or does not exist."
            )
            return

        prompt = await build_interactive_bind_base("asset", asset_id, ctx.guild_id)

        await ctx.response.send(embed=prompt.embed, components=prompt.components)
