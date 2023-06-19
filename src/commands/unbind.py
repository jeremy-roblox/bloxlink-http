from resources.binds import GuildBind, json_binds_to_guild_binds, delete_bind
from resources.bloxlink import instance as bloxlink
from resources.models import CommandContext
from resources.constants import UNICODE_BLANK, REPLY_CONT, REPLY_EMOTE, SPLIT_CHAR
from resources.pagination import Paginator
from resources.component_helper import get_custom_id_data, component_author_validation
import hikari
import re


MAX_BINDS_PER_PAGE = 5


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

    guild_data = await bloxlink.fetch_guild_data(guild_id, "binds")

    paginator = Paginator(
        guild_id,
        user_id,
        guild_data.binds,
        page_number,
        max_items=MAX_BINDS_PER_PAGE,
        custom_formatter=viewbinds_paginator_formatter,
        base_custom_id="unbind:page",
        extra_custom_ids=f"{category}:{id_filter}",
        item_filter=bind_filter(id_filter, category),
    )

    embed = await paginator.embed
    components = paginator.components
    components.add_interactive_button(
        hikari.ButtonStyle.DANGER,
        f"unbind:discard:{user_id}:{category}:{id_filter}",
        label="Discard a bind",
    )

    message.embeds[0] = embed

    await interaction.edit_message(message, embed=embed, components=[components])

    return interaction.build_deferred_response(
        hikari.interactions.base_interactions.ResponseType.DEFERRED_MESSAGE_UPDATE
    )


@component_author_validation(author_segment=3, defer=False)
async def unbind_discard_button(interaction: hikari.ComponentInteraction):
    """Brings up a menu allowing the user to remove bindings."""

    message = interaction.message
    embed = message.embeds[0]

    bind_strings = "\n".join(embed.description.splitlines()[2:])
    numbered_lines = condense_bind_string(bind_strings)
    binds_list = numbered_lines.values()

    if len(binds_list) == 0:
        return (
            interaction.build_response(hikari.ResponseType.MESSAGE_CREATE)
            .set_content("You have no bindings to discard!")
            .set_flags(hikari.MessageFlag.EPHEMERAL)
        )

    embed = hikari.Embed()
    embed.title = "Remove a binding!"
    embed.description = "Choose which binding you want removed from the list above."

    author_id, category, id_option = get_custom_id_data(interaction.custom_id, segment_min=3, segment_max=5)

    selection_menu = bloxlink.rest.build_message_action_row().add_text_menu(
        f"unbind:sel_discard:{message.id}:{author_id}:{category}:{id_option}",
        placeholder="Select which bind should be removed.",
        min_values=0,
    )

    button_menu = bloxlink.rest.build_message_action_row().add_interactive_button(
        hikari.ButtonStyle.SECONDARY, f"unbind:cancel:{author_id}", label="Cancel"
    )

    for x in range(len(binds_list)):
        selection_menu.add_option(f"Bind #{x + 1}", x + 1)

    selection_menu.set_max_values(len(selection_menu.options))

    await interaction.create_initial_response(
        hikari.ResponseType.MESSAGE_CREATE,
        embed=embed,
        components=[selection_menu.parent, button_menu],
        flags=hikari.MessageFlag.EPHEMERAL,
    )


@component_author_validation(author_segment=4, defer=False)
async def unbind_discard_binding(interaction: hikari.ComponentInteraction):
    """Handles the removal of a binding from the list."""

    original_message_id, author_id, category, id_option = get_custom_id_data(
        interaction.custom_id, segment_min=3, segment_max=6
    )

    channel = await interaction.fetch_channel()
    original_message = await channel.fetch_message(original_message_id)

    embed = original_message.embeds[0]
    bind_strings = "\n".join(embed.description.splitlines()[2:])

    bindings_dict = condense_bind_string(bind_strings, join_char=SPLIT_CHAR)
    bindings = list(bindings_dict.values())

    items_to_remove = [bindings[int(item) - 1] for item in interaction.values]

    for item in items_to_remove:
        split = item.split(SPLIT_CHAR)
        split = list(filter(None, split))

        # Get number within parenthesis (anchored to end of str), remove parenthesis
        group_id = re.findall(r"(\(\d{1,}\))$", split[0])[0][1:-1]

        rank_ids = []
        bind_type = ""
        bind_data = {}

        # Non entire-group bindings
        if len(split) > 1:
            rank_str = split[1]
            if "or above:" in rank_str:
                bind_type = "gte"
            elif "or below:" in rank_str:
                bind_type = "lte"
            elif "Non-group members" in rank_str:
                bind_type = "gst"
            elif "All group members" in rank_str:
                bind_type = "all"

            rank_ids = re.findall(r"(\(\d{1,}\))", split[1])
            rank_ids = [int(x[1:-1]) for x in rank_ids]

            if len(rank_ids) == 2:
                bind_type = "rng"
            elif not bind_type:
                bind_type = "equ"

        if bind_type == "equ":
            bind_data["roleset"] = rank_ids[0]
        elif bind_type == "rng":
            bind_data["min"] = rank_ids[0]
            bind_data["max"] = rank_ids[1]
        elif bind_type == "gte":
            # bind_data["min"] = rank_ids[0]
            bind_data["roleset"] = -rank_ids[0]
        elif bind_type == "lte":
            bind_data["max"] = rank_ids[0]
        elif bind_type == "gst":
            bind_data["guest"] = True
        elif bind_type == "all":
            bind_data["everyone"] = True

        await delete_bind(interaction.guild_id, category, group_id, **bind_data)

    guild_data = await bloxlink.fetch_guild_data(interaction.guild_id, "binds")
    paginator = Paginator(
        interaction.guild_id,
        interaction.member.id,
        guild_data.binds,
        max_items=MAX_BINDS_PER_PAGE,
        custom_formatter=viewbinds_paginator_formatter,
        base_custom_id="unbind:page",
        extra_custom_ids=f"{category}:{id_option}",
        item_filter=bind_filter(id_option, category),
    )

    embed = await paginator.embed
    components = paginator.components
    components.add_interactive_button(
        hikari.ButtonStyle.DANGER,
        f"unbind:discard:{author_id}:{category}:{id_option}",
        label="Discard a bind",
    )

    await original_message.edit(embed=embed, components=[components])

    await interaction.create_initial_response(
        hikari.ResponseType.MESSAGE_UPDATE,
        content="Binding removed.",
        embeds=[],
        components=[],
    )


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
        "unbind:discard": unbind_discard_button,
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

        guild_data = await bloxlink.fetch_guild_data(guild_id, "binds")

        paginator = Paginator(
            guild_id,
            user_id,
            max_items=MAX_BINDS_PER_PAGE,
            items=guild_data.binds,
            custom_formatter=viewbinds_paginator_formatter,
            base_custom_id="unbind:page",
            extra_custom_ids=f"{category}:{id_option}",
            item_filter=bind_filter(id_option, category),
        )

        embed = await paginator.embed
        components = paginator.components

        # Only show if there's binds to remove.
        if len(embed.description.splitlines()) > 3:
            components.add_interactive_button(
                hikari.ButtonStyle.DANGER,
                f"unbind:discard:{user_id}:{category}:{id_option}",
                label="Discard a bind",
            )

        await ctx.response.send(embed=embed, components=components)


async def viewbinds_paginator_formatter(page_number, items, guild_id, max_pages):
    embed = hikari.Embed(title="Remove a Binding")

    if len(items) == 0:
        embed.description = (
            "> You have no binds that match the options you passed. "
            "Use `/bind` to make a new binding, or try again with different options."
        )
        return embed

    embed.description = "> Select which bind you want to remove!" f"\n\n"

    output_list = []
    for bind in items:
        bind_str = f"{len(output_list) + 1}. {await bind.get_bind_string(viewbind_styling=True)}"
        output_list.append(bind_str)

    embed.description = embed.description + "\n".join(output_list)

    embed.set_footer(f"Page {page_number + 1}/{max_pages}")

    return embed


def bind_filter(id_filter, category_filter):
    def wrapper(items):
        return json_binds_to_guild_binds(items, category=category_filter, id_filter=id_filter)

    return wrapper


def condense_bind_string(bind_description: str, join_char=" ") -> dict:
    bindings = bind_description.splitlines()

    joined_lines = dict()
    last_digit = 1
    for bind in bindings:
        if bind[0].isdigit():
            last_digit = bind[0]

        bind = bind.replace(REPLY_EMOTE, "")
        bind = bind.replace(REPLY_CONT, "")

        existing_val = joined_lines.get(last_digit, "")
        existing_val += f"{bind}{join_char}"
        joined_lines[last_digit] = existing_val

    return joined_lines
