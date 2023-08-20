import re
from typing import Literal

import hikari
from hikari.commands import CommandOption, OptionType

from resources.binds import create_bind
from resources.bloxlink import instance as bloxlink
from resources.component_helper import (
    component_author_validation,
    get_custom_id_data,
    set_components,
)
from resources.constants import GROUP_RANK_CRITERIA_TEXT, SPLIT_CHAR
from resources.exceptions import RobloxNotFound
from resources.models import CommandContext
from resources.prompts import (
    build_group_criteria_prompt,
    build_interactive_bind_base,
    build_numbered_item_selection,
    build_role_selection_prompt,
    build_roleset_selection_prompt,
)
from resources.roblox.assets import get_asset
from resources.roblox.badges import get_badge
from resources.roblox.gamepasses import get_gamepass
from resources.roblox.groups import get_group

DISCORD_ID_REGEX = r"(\d{17,})"


# ------------------ VVV Bind Flow Component Handlers VVV ------------------


@component_author_validation(author_segment=4, defer=False)
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

    original_message_id, author_id, group_id = get_custom_id_data(
        interaction.custom_id, segment_min=3, segment_max=5
    )

    prompt = None

    if show_roleset_menu:
        value_count = 1 if bind_choice != "rng" else 2
        prompt = await build_roleset_selection_prompt(
            f"{original_message_id}:{author_id}:{bind_choice}",
            group_id,
            author_id,
            min_values=value_count,
            max_values=value_count,
        )
    else:
        # Skip to the role selection prompt.
        # custom_id has double colons because that is where a roleset would go (segment 5).
        prompt = await build_role_selection_prompt(
            f"{original_message_id}:{author_id}::{bind_choice}",
            interaction.guild_id,
            author_id,
            original_message_id,
        )

    await interaction.create_initial_response(
        hikari.ResponseType.MESSAGE_UPDATE, embed=prompt.embed, components=prompt.components
    )


@component_author_validation(author_segment=4, defer=False)
async def bind_menu_select_roleset(interaction: hikari.ComponentInteraction):
    """
    Handles the selected group rank response, one or two depending on the bind condition.
    Sets up role-selection prompt.
    """
    message = interaction.message
    roleset_choices = interaction.values

    original_message_id, author_id, bind_choice = get_custom_id_data(
        interaction.custom_id, segment_min=3, segment_max=5
    )

    # show discord role menu
    roleset_str = (
        f"{roleset_choices[0]}{f'{SPLIT_CHAR}{roleset_choices[1]}' if len(roleset_choices) > 1 else ''}"
    )
    prompt = await build_role_selection_prompt(
        f"{original_message_id}:{author_id}:{roleset_str}:{bind_choice}",
        interaction.guild_id,
        author_id,
        original_message_id,
    )

    message.embeds[0] = prompt.embed
    await set_components(message, components=prompt.components)

    return interaction.build_deferred_response(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)


@component_author_validation(author_segment=4, defer=False)
async def bind_menu_select_role(interaction: hikari.ComponentInteraction):
    """
    Handles the role selection prompt response.

    Saves the values from the prior steps (passed via the component custom_id) and
    the selections from this prompt to the original embed description.
    It then sets up the select roles to remove prompt.
    """
    message = interaction.message

    custom_data = get_custom_id_data(interaction.custom_id, segment_min=3, segment_max=6)
    original_message_id = custom_data[0]
    author_id = custom_data[1]

    is_group_bind = True

    # Depending on user choices, this segment (5) will either be roleset data or the bind type. Determine that here.
    roleset_data = custom_data[2]
    if SPLIT_CHAR in roleset_data:
        roleset_data = roleset_data.split(SPLIT_CHAR)
    elif roleset_data in ("asset", "badge", "gamepass"):
        is_group_bind = False

    # Final segment (6) only exists if this is a group bind.
    if is_group_bind:
        bind_choice = custom_data[3]

    channel = await interaction.fetch_channel()
    original_message = await channel.fetch_message(original_message_id)

    # Save current configuration to the right field.
    # Start by getting the field and then build the updated field value.
    new_description = original_message.embeds[0].fields[1].value.splitlines()

    default_field_str = "*The binds you're making will be added here!*"
    if default_field_str in new_description:
        new_description.remove(default_field_str)

    if "Pending changes:" not in new_description:
        new_description.append("Pending changes:")

    # Generate the bind string for the field.
    prefix = ""
    content = ""

    if is_group_bind:
        prefix = GROUP_RANK_CRITERIA_TEXT.get(bind_choice, "[ERROR] No matching criteria.")
        # "gst" & "all" choices are not handled becuse they have the content included in
        # the prefix string already.
        if bind_choice in ("equ", "gte", "lte"):
            content = roleset_data
        elif bind_choice == "rng":
            min_rank = roleset_data[0]
            max_rank = roleset_data[1]

            content = f"{min_rank}** and **{max_rank}"
    else:
        prefix = "People who own"
        content = f"this {roleset_data}"

    # Discord's role selection shows roles tied to a bot/integration. Don't add those.
    role_list = [
        str(role_id)
        for role_id, role in interaction.resolved.roles.items()
        if role.bot_id == None and role.integration_id == None
    ]

    content = f"**{content}**" if content else ""

    # Check for duplicates in the field & update accordingly. Removes old entry and appends again
    for item in new_description:
        if item[3:].startswith(f"{prefix} {content}"):
            original_roles = []

            # Only get roles to be given, we'll just discard the roles to remove if an entry is there.
            # User can add them back in the next step
            if "these roles removed:" in item:
                split_item = item.split("these roles removed")
                original_roles = re.findall(DISCORD_ID_REGEX, split_item[0])
            else:
                original_roles = re.findall(DISCORD_ID_REGEX, item)

            role_list = list(set(role_list).union(set(original_roles)))

            new_description.remove(item)
            break

    role_mention_str = ", ".join(f"<@&{val}>" for val in role_list)
    new_bind_str = (
        f"- _{prefix} {content} will receive " f"role{'s' if len(role_list) > 1  else ''} {role_mention_str}_"
    )
    new_description.append(new_bind_str)

    # Update title if necessary
    original_title = original_message.embeds[0].title
    original_title = original_title.replace("[SAVED]", "")
    new_title = (
        original_title if "[UNSAVED CHANGES]" in original_title else f"{original_title} [UNSAVED CHANGES]"
    )

    # Update the embed with the new bindings made.
    new_embed = original_message.embeds[0]
    new_embed.title = new_title
    new_embed.fields[1].value = "\n".join(new_description)

    original_message.embeds[0] = new_embed

    # Since a bind has been made, enable the save and discard buttons.
    original_message.components[0][0].is_disabled = False
    original_message.components[0][2].is_disabled = False
    await set_components(original_message)

    # Setup remove role prompt
    prompt = await build_role_selection_prompt(
        custom_id=f"{original_message_id}:{author_id}",
        guild_id=interaction.guild_id,
        author_id=author_id,
        original_message_id=original_message_id,
        placeholder="Choose which role(s) will be removed from people who apply to this bind.",
        skip_button=True,
        remove_text=True,
    )

    message.embeds[0] = prompt.embed
    await set_components(message, components=prompt.components)

    return interaction.build_deferred_response(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)


@component_author_validation(author_segment=4, defer=False)
async def bind_menu_select_remove_roles(interaction: hikari.ComponentInteraction):
    """
    Handles the response from the selection prompt asking if users want roles to be removed.
    """
    original_message_id = get_custom_id_data(interaction.custom_id, segment=3)

    if len(interaction.values) != 0:
        channel = await interaction.fetch_channel()
        original_message = await channel.fetch_message(original_message_id)
        original_embed = original_message.embeds[0]

        original_desc_list = original_embed.fields[1].value.splitlines()
        last_item = original_desc_list[-1]

        role_list = [
            role_id
            for role_id, role in interaction.resolved.roles.items()
            if role.bot_id == None and role.integration_id == None
        ]
        role_mention_str = ", ".join(f"<@&{val}>" for val in role_list)

        last_item = last_item[:-1] + f", and will have these roles removed: {role_mention_str}_"
        original_desc_list[-1] = last_item

        description = "\n".join(original_desc_list)
        original_embed.fields[1].value = description

        await original_message.edit(embed=original_embed)

    await interaction.message.delete()
    return (
        interaction.build_response(hikari.interactions.base_interactions.ResponseType.MESSAGE_CREATE)
        .set_content(
            f"Bind added to your in-progress workflow! "
            f"[Click here](https://discord.com/channels/{interaction.guild_id}/{interaction.channel_id}/{original_message_id})"
            " and click the Save button to save the bind to your server!"
        )
        .set_flags(hikari.MessageFlag.EPHEMERAL)
    )


# ------------------ VVV Primary Bind Prompt Buttons VVV ------------------


@component_author_validation(author_segment=5, defer=False)
async def bind_menu_add_role_button(interaction: hikari.ComponentInteraction):
    """
    Handles what will occur on the add role button press.

    Depending on the bind type, this will do different things, will only be
    applicable for group binds where specific ranks are desired, as well as
    asset, badge, and gamepass bindings.
    """
    custom_id = interaction.custom_id
    message = interaction.message

    # Limit number of binds that can be made to 5 at most in one prompt session before saving.
    field_content = message.embeds[0].fields[1].value.splitlines()
    if len(field_content) > 5:
        response = interaction.build_response(hikari.ResponseType.MESSAGE_CREATE)
        response.set_content(
            "You can only make up to five bindings at once in a prompt! "
            "Please save first before continuing to add more."
        )
        response.set_flags(hikari.MessageFlag.EPHEMERAL)
        return response

    bind_type, bind_id, author_id = get_custom_id_data(custom_id, segment_min=3, segment_max=5)

    prompt = None

    if bind_type == "group":
        if not bind_id:
            return

        group = await get_group(bind_id)

        prompt = build_group_criteria_prompt(f"{message.id}:{author_id}:{bind_id}", author_id)

    elif bind_type in ("asset", "badge", "gamepass"):
        # Direct the user straight to the role selection prompt.
        prompt = await build_role_selection_prompt(
            f"{message.id}:{author_id}:{bind_type}",
            interaction.guild_id,
            author_id,
            message.id,
            process_starter_text=True,
        )

    else:
        raise NotImplementedError(f"The bind type {bind_type} is not handled yet!")

    if prompt:
        await interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE, embed=prompt.embed, components=prompt.components
        )

    return interaction.build_response(hikari.ResponseType.MESSAGE_UPDATE)


@component_author_validation(author_segment=5, defer=False)
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
            interaction.build_response(hikari.ResponseType.MESSAGE_CREATE)
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
            await create_bind(
                guild_id,
                bind_type,
                bind_id=int(prompt_id),
                roles=role_ids,
                remove_roles=remove_role_ids,
            )

    prompt = await build_interactive_bind_base(
        bind_type, prompt_id, interaction.guild_id, interaction.member.id, disable_save=True
    )
    prompt.embed.title += " [SAVED]"
    await message.edit(embed=prompt.embed, component=prompt.components)

    return (
        interaction.build_response(hikari.interactions.base_interactions.ResponseType.MESSAGE_CREATE)
        .set_content("Your bindings have been saved!")
        .set_flags(hikari.MessageFlag.EPHEMERAL)
    )


@component_author_validation(author_segment=3, defer=False)
async def bind_menu_discard_button(interaction: hikari.ComponentInteraction):
    """Brings up a menu allowing the user to remove bindings from the new embed field."""

    message = interaction.message
    embed = message.embeds[0]
    new_binds_field = embed.fields[1]
    bindings = new_binds_field.value.splitlines()[1:]

    if len(bindings) == 0:
        return (
            interaction.build_response(hikari.ResponseType.MESSAGE_CREATE)
            .set_content("You have no new bindings to discard!")
            .set_flags(hikari.MessageFlag.EPHEMERAL)
        )

    author_id = get_custom_id_data(custom_id=interaction.custom_id, segment=3)
    prompt = build_numbered_item_selection(f"{message.id}:{author_id}", bindings, author_id)
    await interaction.create_initial_response(
        hikari.ResponseType.MESSAGE_CREATE,
        embed=prompt.embed,
        components=prompt.components,
        flags=hikari.MessageFlag.EPHEMERAL,
    )


# ------------------ VVV Additional/Misc Component Handlers VVV ------------------


@component_author_validation(author_segment=4, defer=False)
async def bind_menu_discard_binding(interaction: hikari.ComponentInteraction):
    """Handles the removal of a binding from the list."""

    original_message_id = get_custom_id_data(interaction.custom_id, segment=3)
    channel = await interaction.fetch_channel()
    original_message = await channel.fetch_message(original_message_id)

    embed = original_message.embeds[0]
    binds_field = embed.fields[1]
    bindings = binds_field.value.splitlines()

    first_line = bindings[0]
    bindings = bindings[1:]

    items_to_remove = [bindings[int(item) - 1] for item in interaction.values]
    for item in items_to_remove:
        bindings.remove(item)

    if len(bindings) == 0:
        embed.title = embed.title.replace("[UNSAVED CHANGES]", "").strip()
        bindings.append("*The binds you're making will be added here!*")
        original_message.components[0][0].is_disabled = True
        original_message.components[0][2].is_disabled = True
    else:
        bindings.insert(0, first_line)

    binds_field.value = "\n".join(bindings)

    await set_components(original_message)

    await interaction.create_initial_response(
        hikari.ResponseType.MESSAGE_UPDATE,
        content="Binding removed.",
        embeds=[],
        components=[],
    )


@component_author_validation(author_segment=3, defer=False)
async def bind_menu_cancel_button(interaction: hikari.ComponentInteraction):
    # Inferring that the only place we're allowed to skip is the role removal prompt.
    # Can't link to the original message unless we start passing along the original message id
    # to the cancel button custom_id

    original_message_id = get_custom_id_data(interaction.custom_id, segment=4)
    message_string = (
        f"https://discord.com/channels/{interaction.guild_id}/{interaction.channel_id}/{original_message_id}"
    )

    response = (
        "Your prompt has been cancelled."
        if "cancel" in interaction.custom_id
        else (
            f"Bind added to your in-progress workflow! "
            f"[Click here]({message_string}) and click the Save button to save the bind to your server!"
        )
    )

    if interaction.message.flags & hikari.MessageFlag.EPHEMERAL == hikari.MessageFlag.EPHEMERAL:
        await interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_UPDATE, content=response, components=[], embeds=[]
        )

        return interaction.build_response(hikari.ResponseType.MESSAGE_UPDATE)
    else:
        await bloxlink.rest.delete_message(interaction.channel_id, interaction.message)

    return (
        interaction.build_response(hikari.ResponseType.MESSAGE_CREATE)
        .set_content(response)
        .set_flags(hikari.MessageFlag.EPHEMERAL)
    )


# ------------------ VVV Command/Subcommands VVV ------------------


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
        "bind_menu:discard_button": bind_menu_discard_button,
        "bind_menu:discard_selection": bind_menu_discard_binding,
        "bind_menu:cancel": bind_menu_cancel_button,
        "bind_menu:skip": bind_menu_cancel_button,
    },
    dm_enabled=False,
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
            prompt = await build_interactive_bind_base("group", group_id, ctx.guild_id, ctx.member.id, True)

            await ctx.response.send(embed=prompt.embed, components=prompt.components)

        elif bind_mode == "entire_group":
            # Isn't interactive - just makes the binding and tells the user if it worked or not.
            # TODO: ask if the bot can create roles that match their group rolesets

            try:
                await create_bind(ctx.guild_id, bind_type="group", bind_id=group_id)
            except NotImplementedError:
                await ctx.response.send(
                    f"You already have a group binding for group [{group.name}](<https://www.roblox.com/groups/{group.id}/->). No changes were made."
                )
                return

            await ctx.response.send(
                f"Your group binding for group [{group.name}](https://www.roblox.com/groups/{group.id}/-) has been saved. "
                "When people join your server, they will receive a Discord role that corresponds to their group rank. "
            )

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

        await self._handle_command(ctx, "asset")

    @bloxlink.subcommand(
        options=[
            CommandOption(
                type=OptionType.INTEGER,
                name="badge_id",
                description="What is your badge ID?",
                is_required=True,
            )
        ]
    )
    async def badge(self, ctx: CommandContext):
        """Bind a badge to your server"""

        await self._handle_command(ctx, "badge")

    @bloxlink.subcommand(
        options=[
            CommandOption(
                type=OptionType.INTEGER,
                name="gamepass_id",
                description="What is your gamepass ID?",
                is_required=True,
            )
        ]
    )
    async def gamepass(self, ctx: CommandContext):
        """Bind a gamepass to your server"""

        await self._handle_command(ctx, "gamepass")

    async def _handle_command(
        self,
        ctx: CommandContext,
        cmd_type: Literal["group", "asset", "badge", "gamepass"],
    ):
        """
        Handle initial command input and response.

        It is primarily intended to be used for the asset, badge, and gamepass types.
        The group command is handled by itself in its respective command method.
        """
        match cmd_type:
            case "group":
                # Placeholder in case we ever move group input handling here.
                pass
            case "asset" | "badge" | "gamepass":
                input_id = ctx.options[f"{cmd_type}_id"]

                try:
                    match cmd_type:
                        case "asset":
                            await get_asset(input_id)
                        case "badge":
                            await get_badge(input_id)
                        case "gamepass":
                            await get_gamepass(input_id)
                except RobloxNotFound:
                    # Can't be ephemeral sadly bc of the defer state for the command.
                    await ctx.response.send(
                        f"The {cmd_type} ID ({input_id}) you gave is either invalid or does not exist."
                    )
                    return

                prompt = await build_interactive_bind_base(
                    cmd_type, input_id, ctx.guild_id, ctx.member.id, True
                )

                await ctx.response.send(embed=prompt.embed, components=prompt.components)
