from resources.binds import GuildBind, json_binds_to_guild_binds
from resources.bloxlink import instance as bloxlink
from resources.groups import get_group
from resources.models import CommandContext
from resources.constants import RED_COLOR, UNICODE_BLANK
from resources.pagination import Paginator
from resources.component_helper import get_custom_id_data, set_components, component_author_validation
from resources.exceptions import RobloxAPIError
import hikari


MAX_BINDS_PER_PAGE = 5


async def viewbinds_category_autocomplete(interaction: hikari.AutocompleteInteraction):
    guild_data = await bloxlink.fetch_guild_data(interaction.guild_id, "binds")

    bind_types = set(bind["bind"]["type"] for bind in guild_data.binds)

    return interaction.build_response(
        [hikari.impl.AutocompleteChoiceBuilder(c.title(), c) for c in bind_types]
    )


async def viewbinds_id_autocomplete(interaction: hikari.AutocompleteInteraction):
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
                if str(x.id).startswith(id_option)
            )
        else:
            filtered_binds = set(x.id for x in [GuildBind(**bind) for bind in guild_data.binds])

        for bind in filtered_binds:
            choices.append(hikari.impl.AutocompleteChoiceBuilder(str(bind), str(bind)))

    # Due to discord limitations, only return the first 25 choices.
    return interaction.build_response(choices[:25])


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
        guild_data.binds,
        page_number,
        max_items=MAX_BINDS_PER_PAGE,
        custom_formatter=viewbinds_paginator_formatter,
        extra_custom_ids=f"{category}:{id_filter}",
        item_filter=viewbinds_item_filter(id_filter, category),
    )

    embed = await paginator.embed
    components = paginator.components

    message.embeds[0] = embed

    # Handles emojis as expected
    await interaction.edit_message(message, embed=embed, components=[components])

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
        "category": viewbinds_category_autocomplete,
        "id": viewbinds_id_autocomplete,
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
            max_items=MAX_BINDS_PER_PAGE,
            items=guild_data.binds,
            custom_formatter=viewbinds_paginator_formatter,
            extra_custom_ids=f"{category}:{id_option}",
            item_filter=viewbinds_item_filter(id_option, category),
        )

        embed = await paginator.embed
        components = paginator.components

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

        bind_string = await bind.get_bind_string(
            guild_id=guild_id, include_id=include_id, include_name=include_id
        )

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
