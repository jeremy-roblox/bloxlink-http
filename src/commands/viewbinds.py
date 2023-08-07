import hikari

from resources.autocomplete import bind_category_autocomplete, bind_id_autocomplete
from resources.binds import json_binds_to_guild_binds
from resources.bloxlink import instance as bloxlink
from resources.component_helper import component_author_validation, get_custom_id_data
from resources.constants import RED_COLOR, UNICODE_BLANK
from resources.exceptions import RobloxAPIError
from resources.groups import get_group
from resources.models import CommandContext
from resources.pagination import Paginator

MAX_BINDS_PER_PAGE = 5


@component_author_validation()
async def viewbinds_button(interaction: hikari.ComponentInteraction):
    message = interaction.message

    custom_id_data = get_custom_id_data(interaction.custom_id, segment_min=2)

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
        source_cmd_name="viewbinds",
        max_items=MAX_BINDS_PER_PAGE,
        items=guild_data.binds,
        page_number=page_number,
        custom_formatter=viewbinds_paginator_formatter,
        extra_custom_ids=f"{category}:{id_filter}",
        item_filter=viewbinds_item_filter(id_filter, category),
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
class ViewBindsCommand:
    """View your binds for your server"""

    async def __main__(self, ctx: CommandContext):
        category = ctx.options["category"]
        id_option = ctx.options["id"]

        guild_id = ctx.guild_id
        user_id = ctx.user.id

        guild_data = await bloxlink.fetch_guild_data(guild_id, "binds")

        paginator = Paginator(
            guild_id,
            user_id,
            source_cmd_name="viewbinds",
            max_items=MAX_BINDS_PER_PAGE,
            items=guild_data.binds,
            custom_formatter=viewbinds_paginator_formatter,
            extra_custom_ids=f"{category}:{id_option}",
            item_filter=viewbinds_item_filter(id_option, category),
        )

        embed = await paginator.embed
        components = await paginator.components

        await ctx.response.send(embed=embed, components=components)


async def viewbinds_paginator_formatter(page_number, items, guild_id, max_pages):
    embed = hikari.Embed(title="Bloxlink Role Binds")

    if len(items) == 0:
        embed.description = (
            "> You have no binds that match the options you passed. "
            "Use `/bind` to make a new binding, or try again with different options."
        )
        return embed

    item_map = {
        "linked_group": [],
        "group_roles": {},
        "asset": [],
        "badge": [],
        "gamepass": [],
    }

    for bind in items:
        bind_type = bind.determine_type()
        include_id = True if bind_type != "group_roles" else False

        bind_string = await bind.get_bind_string(include_id=include_id, include_name=include_id)

        for types in item_map:
            if types == "group_roles" and bind_type == types:
                select_output = item_map[types].get(bind.id, [])
                select_output.append(bind_string)
                item_map[types][bind.id] = select_output
            elif bind_type == types:
                item_map[types].append(bind_string)

    # TODO: Probably should either move the above logic out of here,
    # and/or bring the build_page_embed logic into here.
    return await build_page_embed(item_map, page_number, max_pages)


def viewbinds_item_filter(id_filter, category_filter):
    def wrapper(items):
        return json_binds_to_guild_binds(items, category=category_filter, id_filter=id_filter)

    return wrapper


async def build_page_embed(page_components, page_num, page_max) -> hikari.Embed:
    embed = hikari.Embed()
    embed.title = "**Bloxlink Role Binds**"

    embed.color = RED_COLOR
    embed.description = (
        "Use </bind:836429412810358807> to make a new bind, "
        f"or </unbind:836429412810358805> to delete a bind.\n{UNICODE_BLANK}"
    )
    embed.set_footer(f"Page {page_num + 1}/{page_max}")

    if page_components["linked_group"]:
        embed.add_field("Linked Groups", "\n".join(page_components["linked_group"]), inline=True)

    if page_components["group_roles"]:
        rank_map = page_components["group_roles"]
        for group in rank_map.keys():
            try:
                embed.add_field(
                    f"{(await get_group(group)).name} ({group})",
                    "\n".join(rank_map[group]),
                    inline=True,
                )
            except RobloxAPIError:
                embed.add_field(f"*Invalid Group* ({group})", "\n".join(rank_map[group]), inline=True)

    if page_components["asset"]:
        embed.add_field("Assets", "\n".join(page_components["asset"]))

    if page_components["badge"]:
        embed.add_field("Badges", "\n".join(page_components["badge"]))

    if page_components["gamepass"]:
        embed.add_field("Gamepasses", "\n".join(page_components["gamepass"]))

    return embed
