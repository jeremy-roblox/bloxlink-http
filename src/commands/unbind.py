import json
import math

import hikari

from resources.binds import (
    GuildBind,
    delete_bind,
    json_binds_to_guild_binds,
    named_string_builder,
    roleset_to_string,
)
from resources.bloxlink import instance as bloxlink
from resources.component_helper import component_author_validation, get_custom_id_data
from resources.constants import UNICODE_LEFT, UNICODE_RIGHT
from resources.models import CommandContext

MAX_BINDS_PER_PAGE = 15


async def unbind_category_autocomplete(interaction: hikari.AutocompleteInteraction):
    guild_data = await bloxlink.fetch_guild_data(interaction.guild_id, "binds")

    bind_types = set(bind["bind"]["type"] for bind in guild_data.binds)

    return interaction.build_response(
        [hikari.impl.AutocompleteChoiceBuilder(c.title(), c) for c in bind_types]
    )


async def unbind_id_autocomplete(interaction: hikari.AutocompleteInteraction):
    choices = [
        # base option
        hikari.impl.AutocompleteChoiceBuilder("View all your bindings", "View binds")
    ]

    options = {o.name.lower(): o for o in interaction.options}

    category_option = options.get("category")
    id_option = options.get("id").value.lower() if options.get("id") else None

    # Only show more options if the category option has been set by the user.
    if category_option:
        guild_data = await bloxlink.fetch_guild_data(interaction.guild_id, "binds")

        # Conversion to GuildBind is because it's easier to get the typing for filtering.
        if id_option:
            filtered_binds = set(
                x.id
                for x in [GuildBind(**bind) for bind in guild_data.binds]
                if str(x.id).startswith(id_option) and x.type == category_option.value
            )
        else:
            filtered_binds = set(
                x.id
                for x in [GuildBind(**bind) for bind in guild_data.binds]
                if x.type == category_option.value
            )

        for bind in filtered_binds:
            choices.append(hikari.impl.AutocompleteChoiceBuilder(str(bind), str(bind)))

    # Due to discord limitations, only return the first 25 choices.
    return interaction.build_response(choices[:25])


@component_author_validation(author_segment=3)
async def unbind_pagination_button(interaction: hikari.ComponentInteraction):
    message = interaction.message

    custom_id_data = get_custom_id_data(interaction.custom_id, segment_min=3)

    author_id = int(custom_id_data[0])
    page_number = int(custom_id_data[1])

    category = custom_id_data[2]
    id_filter = custom_id_data[3]

    guild_id = interaction.guild_id
    user_id = interaction.user.id

    embed, components = await paginator_formatter(
        page_number,
        guild_id=guild_id,
        author_id=author_id,
        category=category,
        id_filter=id_filter,
    )

    await interaction.edit_message(message, embed=embed, components=components)

    return interaction.build_deferred_response(
        hikari.interactions.base_interactions.ResponseType.DEFERRED_MESSAGE_UPDATE
    )


@component_author_validation(author_segment=3, defer=False)
async def unbind_discard_binding(interaction: hikari.ComponentInteraction):
    """Handles the removal of a binding from the list."""

    await interaction.create_initial_response(
        hikari.ResponseType.DEFERRED_MESSAGE_CREATE, flags=hikari.MessageFlag.EPHEMERAL
    )

    author_id, category, id_option = get_custom_id_data(interaction.custom_id, segment_min=3, segment_max=6)

    for item in interaction.values:
        split = item.split(":", maxsplit=1)

        bind_id = int(split[0])
        bind_data = json.loads(split[1]) if len(split) > 1 else {}

        await delete_bind(interaction.guild_id, category, bind_id, **bind_data)

    # Reset the prompt to page 0.
    embed, components = await paginator_formatter(
        0,
        guild_id=interaction.guild_id,
        author_id=author_id,
        category=category,
        id_filter=id_option,
    )

    await bloxlink.rest.edit_message(
        interaction.channel_id, interaction.message.id, embed=embed, components=components
    )
    await interaction.edit_initial_response("Your chosen bindings have been removed.")

    return interaction.build_deferred_response(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)


@component_author_validation(author_segment=3, defer=False)
async def unbind_cancel_button(interaction: hikari.ComponentInteraction):
    if interaction.message.flags & hikari.MessageFlag.EPHEMERAL == hikari.MessageFlag.EPHEMERAL:
        await interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_UPDATE, content="Prompt cancelled.", components=[], embeds=[]
        )

        return interaction.build_response(hikari.ResponseType.MESSAGE_UPDATE)
    else:
        await bloxlink.rest.delete_message(interaction.channel_id, interaction.message)

    return (
        interaction.build_response(hikari.ResponseType.MESSAGE_CREATE)
        .set_content("Prompt cancelled.")
        .set_flags(hikari.MessageFlag.EPHEMERAL)
    )


@bloxlink.command(
    category="Administration",
    defer=True,
    permissions=hikari.Permissions.MANAGE_GUILD,
    options=[
        hikari.commands.CommandOption(
            type=hikari.commands.OptionType.STRING,
            name="category",
            description="Choose what type of binds you want to see.",
            is_required=True,
            autocomplete=True,
        ),
        hikari.commands.CommandOption(
            type=hikari.commands.OptionType.STRING,
            name="id",
            description="Select which ID you want to see your bindings for.",
            is_required=True,
            autocomplete=True,
        ),
    ],
    accepted_custom_ids={
        "unbind:page": unbind_pagination_button,
        "unbind:sel_discard": unbind_discard_binding,
        "unbind:cancel": unbind_cancel_button,
    },
    autocomplete_handlers={
        "category": unbind_category_autocomplete,
        "id": unbind_id_autocomplete,
    },
    dm_enabled=False,
)
class UnbindCommand:
    """Delete some binds from your server"""

    async def __main__(self, ctx: CommandContext):
        category = ctx.options["category"]
        id_option = ctx.options["id"]

        guild_id = ctx.guild_id
        user_id = ctx.user.id

        embed, components = await paginator_formatter(
            0,
            guild_id=guild_id,
            author_id=user_id,
            category=category,
            id_filter=id_option,
        )

        await ctx.response.send(embed=embed, components=components)


# Not using the paginator class since we can't customize components easily there
# without much more revamping.
async def paginator_formatter(page_number, guild_id, author_id, category, id_filter):
    guild_data = await bloxlink.fetch_guild_data(guild_id, "binds")
    items = json_binds_to_guild_binds(guild_data.binds, category=category, id_filter=id_filter)

    embed = hikari.Embed(title="Remove a Binding")

    if len(items) == 0:
        embed.description = (
            "> You have no binds that match the options you passed. "
            "Use `/bind` to make a new binding, or try again with different options."
        )
        return embed, []

    embed.description = f"**Select which bind you want to remove from the menu below!**"

    if len(items) > MAX_BINDS_PER_PAGE:
        embed.description += (
            "\n\n> Don't see the bind you're looking for? "
            "Use the buttons below to have the menu scroll to a new page."
        )

    offset = page_number * MAX_BINDS_PER_PAGE
    max_items = len(items) if (offset + MAX_BINDS_PER_PAGE >= len(items)) else offset + MAX_BINDS_PER_PAGE

    selection_menu = bloxlink.rest.build_message_action_row().add_text_menu(
        f"unbind:sel_discard:{author_id}:{category}:{id_filter}",
        placeholder="Select which bind should be removed.",
        min_values=1,
    )

    output_list = items[offset:max_items]
    for bind in output_list:
        bind_type = bind.determine_type()

        if bind_type == "linked_group":
            name = await named_string_builder(bind.type, bind.id, include_id=True, include_name=True)
            name = name.replace("**", "")
            selection_menu.add_option(
                name,
                str(bind.id),
                description="This is a linked group binding.",
            )
        elif bind_type == "group_roles":
            bind_data = {}

            label = ""
            group_name = await named_string_builder(bind.type, bind.id, include_id=True, include_name=True)
            group_name = group_name.replace("**", "")
            description = f"Group: {group_name}"

            if bind.everyone:
                bind_data["everyone"] = bind.everyone
                label = "All group members"
            elif bind.guest:
                bind_data["guest"] = bind.guest
                label = "Non-group members"
            elif bind.min and bind.max:
                bind_data["min"] = bind.min
                bind_data["max"] = bind.max

                min_name = await roleset_to_string(bind.id, bind.min)
                max_name = await roleset_to_string(bind.id, bind.max)

                label = f"Ranks {min_name} to {max_name}"
            elif bind.min:
                bind_data["min"] = bind.min

                min_name = await roleset_to_string(bind.id, bind.min)
                label = f"Rank {min_name} or above"
                pass
            elif bind.max:
                bind_data["max"] = bind.max

                max_name = await roleset_to_string(bind.id, bind.max)
                label = f"Rank {max_name} or below"
            elif bind.roleset:
                bind_data["roleset"] = bind.roleset

                name = await roleset_to_string(bind.id, abs(bind.roleset))
                if bind.roleset < 0:
                    label = f"Rank {name} or above"
                else:
                    label = f"Rank {name}"

            selection_menu.add_option(
                label[:100],
                f"{str(bind.id)}:{json.dumps(bind_data, separators=(',', ':'))}",
                description=description,
            )
        else:
            name = await named_string_builder(bind.type, bind.id, include_id=True, include_name=True)
            name = name.replace("**", "")
            selection_menu.add_option(name, str(bind.id))

    selection_menu.set_max_values(len(selection_menu.options))

    button_row = bloxlink.rest.build_message_action_row()
    # Previous button
    button_row.add_interactive_button(
        hikari.ButtonStyle.SECONDARY,
        f"unbind:page:{author_id}:{page_number-1}:{category}:{id_filter}",
        label=UNICODE_LEFT,
        is_disabled=True if page_number == 0 else False,
    )

    # Next button
    button_row.add_interactive_button(
        hikari.ButtonStyle.SECONDARY,
        f"unbind:page:{author_id}:{page_number+1}:{category}:{id_filter}",
        label=UNICODE_RIGHT,
        is_disabled=True if len(output_list) != MAX_BINDS_PER_PAGE else False,
    )

    button_row.add_interactive_button(
        hikari.ButtonStyle.SECONDARY, f"unbind:cancel:{author_id}", label="Cancel"
    )

    max_pages = math.ceil(len(items) / MAX_BINDS_PER_PAGE)
    embed.set_footer(f"Page {page_number + 1}/{max_pages}")

    return embed, [selection_menu.parent, button_row]
