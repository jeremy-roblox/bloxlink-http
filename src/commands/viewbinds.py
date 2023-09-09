import hikari

from resources.autocomplete import bind_category_autocomplete, bind_id_autocomplete
from resources.binds import join_bind_strings, json_binds_to_guild_binds
from resources.bloxlink import instance as bloxlink
from resources.component_helper import component_author_validation, get_custom_id_data
from resources.constants import RED_COLOR, UNICODE_BLANK
from resources.exceptions import RobloxAPIError, RobloxNotFound
from resources.models import CommandContext, GroupBind, GuildBind
from resources.pagination import Paginator

MAX_BINDS_PER_PAGE = 5


@component_author_validation(author_segment=3)
async def viewbinds_button(interaction: hikari.ComponentInteraction):
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


async def viewbinds_paginator_formatter(page_number: int, items: list, _guild_id: str | int, max_pages: int):
    """Generates the components for the viewbinds page, and then calls build_page_embed.

    Args:
        page_number (int): The page number of the page to build.
        items (list): The bindings to show in the page.
        _guild_id (str | int): Unused, the ID of the guild that the command was run in.
        max_pages (int): The page number of the last page that can be built.

    Returns:
        hikari.Embed: The formatted embed as built by build_page_embed.
    """
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
        "group_names": {},
        "asset": [],
        "badge": [],
        "gamepass": [],
    }

    for bind in items:
        if bind.type == "group":
            subtype = bind.subtype
        else:
            subtype = bind.type

        bind_string = await _bind_string_gen(bind)

        if subtype == "group_roles":
            select_output = item_map[subtype].get(bind.id, [])
            select_output.append(bind_string)
            item_map[subtype][bind.id] = select_output

            if bind.id not in item_map["group_names"]:
                item_map["group_names"][bind.id] = str(bind.entity)
        else:
            item_map[subtype].append(bind_string)

    # TODO: Probably should either move the above logic out of here,
    # and/or bring the build_page_embed logic into here.
    return await build_page_embed(item_map, page_number, max_pages)


async def _bind_string_gen(bind: GroupBind | GuildBind) -> str:
    """Convert a GroupBind or GuildBind to a string format for the viewbind prompt.

    Args:
        bind (GroupBind | GuildBind): The binding to build a string for.

    Returns:
        str: The formatted string for the viewbind prompt.
    """
    entity = bind.entity
    if not entity.synced:
        try:
            await entity.sync()
        except RobloxAPIError:
            pass
        except RobloxNotFound:
            pass

    name_id_string = str(entity)

    role_string = None
    if bind.roles:
        # Only build role_string if there are roles.
        role_string = ", ".join([f"<@&{role}>" for role in bind.roles])
        role_string = f"Role(s): {role_string}"

    if isinstance(bind, GroupBind):
        if bind.subtype == "linked_group":
            # Role strings don't exist for linked groups.
            role_string = None
        else:
            # Don't include group name + id for roleset binds.
            name_id_string = None

    nickname_string = f"Nickname: `{bind.nickname}`" if bind.nickname else None

    remove_role_str = None
    if bind.removeRoles and (bind.removeRoles != "null" or bind.removeRoles != "undefined"):
        remove_role_str = "Remove Roles:" + ", ".join([f"<@&{role}>" for role in bind.removeRoles])

    rank_string = None
    if isinstance(bind, GroupBind):
        rank_string = _groupbind_rank_generator(bind)

    # Combine everything and remove the unused strings.
    output_list = list(
        filter(None, [name_id_string, rank_string, role_string, nickname_string, remove_role_str])
    )
    return join_bind_strings(output_list)


def _groupbind_rank_generator(bind: GroupBind) -> str:
    """Handle the name determination of what rank string should be shown for a group binding.

    Args:
        bind (GroupBind): Binding to build a rank string for.

    Returns:
        str: The parsed rank string.
    """
    if not bind.roles:
        return None

    if bind.subtype == "linked_group":
        return None

    rank_string = ""
    group = bind.entity

    if bind.min is not None and bind.max is not None:
        min_str = group.roleset_name_string(bind.min)
        max_str = group.roleset_name_string(bind.max)

        rank_string = f"Ranks {min_str} to {max_str}:"

    elif bind.min is not None:
        min_str = group.roleset_name_string(bind.min)
        rank_string = f"Rank {min_str} or above:"

    elif bind.max is not None:
        max_str = group.roleset_name_string(bind.max)
        rank_string = f"Rank {max_str} or below:"

    elif bind.roleset is not None:
        abs_roleset = abs(bind.roleset)
        roleset_str = group.roleset_name_string(abs_roleset)

        if bind.roleset <= 0:
            rank_string = f"Rank {roleset_str} or above:"
        else:
            rank_string = f"Rank {roleset_str}:"

    elif bind.everyone:
        rank_string = "**All group members**:"

    elif bind.guest:
        rank_string = "**Non-group members**:"

    return rank_string


def viewbinds_item_filter(id_filter: str | int, category_filter: str):
    """Wrap the filter function for pagination to allow for additional parameter passing.

    Args:
        id_filter (str | int): ID to filter the binds by.
        category_filter (str): Category to filter the binds by.
    """

    def wrapper(items):
        return json_binds_to_guild_binds(items, category=category_filter, id_filter=id_filter)

    return wrapper


async def build_page_embed(page_components: dict, page_num: int, page_max: int) -> hikari.Embed:
    """Build a page for the viewbind prompt.

    Args:
        page_components (dict): Components to build the page with.
        page_num (int): The page number to generate.
        page_max (int): The maximum number of pages available, used for footer generation.

    Returns:
        hikari.Embed: The formatted page for page_num.
    """
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
            group_name = page_components["group_names"].get(group, f"*(Invalid Group)* ({group})")

            embed.add_field(
                group_name,
                "\n".join(rank_map[group]),
                inline=True,
            )

    if page_components["asset"]:
        embed.add_field("Assets", "\n".join(page_components["asset"]))

    if page_components["badge"]:
        embed.add_field("Badges", "\n".join(page_components["badge"]))

    if page_components["gamepass"]:
        embed.add_field("Gamepasses", "\n".join(page_components["gamepass"]))

    return embed
