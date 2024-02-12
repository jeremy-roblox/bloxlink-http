import hikari

from bloxlink_lib import GuildBind, get_binds

from resources.ui.autocomplete import bind_category_autocomplete, bind_id_autocomplete
from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.ui.components import component_author_validation, get_custom_id_data
from resources.pagination import Paginator

MAX_BINDS_PER_PAGE = 5


@component_author_validation(author_segment=3)
async def viewbinds_button(ctx: CommandContext):
    """Handle pagination left and right button presses."""
    interaction = ctx.interaction
    message = interaction.message

    custom_id_data = get_custom_id_data(interaction.custom_id, segment_min=3)

    author_id = int(custom_id_data[0])
    page_number = int(custom_id_data[1])

    category = custom_id_data[2]
    id_filter = custom_id_data[3]

    guild_id = interaction.guild_id

    guild_data = await get_binds(guild_id, bind_id=id_filter, category=category)

    paginator = Paginator(
        guild_id,
        author_id,
        command_name="viewbinds",
        max_items=MAX_BINDS_PER_PAGE,
        items=guild_data,
        page_number=page_number,
        custom_formatter=viewbinds_paginator_formatter,
        extra_custom_ids=f"{category}:{id_filter}",
        item_filter=viewbinds_item_filter,
    )

    embed = await paginator.embed
    components = await paginator.components

    message.embeds[0] = embed

    # Handles emojis as expected
    await interaction.edit_message(message, embed=embed, components=components)

    # TODO: Breaks emojis in the reply somehow?
    # await set_components(message, components=[components])

    return interaction.build_deferred_response(
        hikari.interactions.base_interactions.ResponseType.DEFERRED_MESSAGE_UPDATE
    )


@bloxlink.command(
    category="Account",
    defer=True,
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
        "viewbinds": viewbinds_button,
    },
    autocomplete_handlers={
        "category": bind_category_autocomplete,
        "id": bind_id_autocomplete,
    },
)
class ViewBindsCommand(GenericCommand):
    """View your binds for your server"""

    async def __main__(self, ctx: CommandContext):
        category = ctx.options["category"]
        id_option = ctx.options["id"]

        guild_id = ctx.guild_id
        user_id = ctx.user.id

        guild_binds = await get_binds(guild_id, bind_id=int(id_option) if id_option.isdigit() else None, category=category)

        paginator = Paginator(
            guild_id,
            user_id,
            command_name="viewbinds",
            max_items=MAX_BINDS_PER_PAGE,
            items=guild_binds,
            custom_formatter=viewbinds_paginator_formatter,
            extra_custom_ids=f"{category}:{id_option}", # TODO: use the CustomID class
            item_filter=viewbinds_item_filter,
        )

        embed = await paginator.embed
        components = await paginator.components

        await ctx.response.send(embed=embed, components=components, build_components=False)


async def viewbinds_paginator_formatter(page_number: int, items: list[GuildBind], _guild_id: str | int, max_pages: int):
    """Generates the components for the viewbinds page.

    Args:
        page_number (int): The page number of the page to build.
        items (list): The bindings to show on the page.
        _guild_id (str | int): Unused, the ID of the guild that the command was run in.
        max_pages (int): The page number of the last page that can be built.

    Returns:
        hikari.Embed: The formatted embed.
    """

    bind_list: dict[str, list[str]] = {}

    embed = hikari.Embed(title="Bloxlink Role Binds")
    embed.set_footer(f"Page {page_number + 1}/{max_pages}")

    if not items:
        embed.description = (
            "> You have no binds that match the options you passed. "
            "Use `/bind` to make a new binding, or try again with different options."
        )
        return embed

    embed.description = (
        "Use </bind:836429412810358807> to make a new bind, " # FIXME: command IDs
        "or </unbind:836429412810358805> to delete a bind."
    )

    for bind in items:
        await bind.entity.sync()

        bind_entity = str(bind.entity)

        if bind_entity not in bind_list:
            bind_list[bind_entity] = []

        bind_list[bind_entity].append(str(bind))

    for bind_entity, bind_strings in bind_list.items():
        embed.add_field(name=bind_entity, value="\n".join(bind_strings))

    return embed

def viewbinds_item_filter(items: list[GuildBind]):
    """Sorts the given binds."""

    return sorted(items, key=lambda item: item.criteria.id)
