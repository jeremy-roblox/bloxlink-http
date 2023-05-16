from resources.binds import GuildBind, json_binds_to_guild_binds
from resources.bloxlink import instance as bloxlink
from resources.groups import get_group
from resources.models import CommandContext
from resources.constants import RED_COLOR
from resources.pagination import pagination_validation
from resources.component_helper import get_custom_id_data, set_components
from resources.exceptions import RobloxAPIError
import hikari


MAX_BINDS_PER_PAGE = 2


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


# @pagination_validation(timeout_mins=15)
# async def viewbinds_button(interaction: hikari.ComponentInteraction):
#     """Handles the pagination buttons for viewbinds. Since the custom_id includes the next page,
#     we only need one method to handle both buttons."""

#     # get_custom_id_data starts at segment 1, data we care about starts at 2 (author ID +)
#     custom_id_data = get_custom_id_data(interaction.custom_id, segment_min=2)

#     author_id = custom_id_data[0]
#     page_number = custom_id_data[1]
#     category = custom_id_data[2]
#     id_filter = custom_id_data[3]

#     page = await build_page_components(
#         interaction.guild_id, int(author_id), category, int(page_number), id_filter
#     )
#     embed = await build_page_embed(page)

#     # Update the embed.
#     await interaction.edit_message(interaction.message, embed=embed, components=[page["button_row"]])


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
        custom_formatter=viewbinds_paginator_formatter(id_filter, category),
        extra_custom_ids=f"{category}:{id_filter}",
    )

    embed = paginator.embed
    components = paginator.components

    message.embeds[0] = embed

    await set_components(message, components=[components])

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
            custom_formatter=viewbinds_paginator_formatter(id_option, category),
            extra_custom_ids=f"{category}:{id_option}",
        )

        embed = paginator.embed
        components = paginator.components

        await ctx.response.send(embed=embed, components=components)


def viewbinds_paginator_formatter(id_filter, category_filter):
    def wrapper(page_number, items):
        embed = hikari.Embed(title="Bloxlink Role Binds")

        embed.description = "\n".join(
            [
                f"bind id {bind['bind']['id']}"
                for bind in items
                if (
                    bind["bind"]["type"] == category_filter
                    and (id_filter and str(bind["bind"]["id"]) == id_filter or True)
                )
            ]
        )

        return embed

    return wrapper


class Paginator:
    def __init__(
        self,
        guild_id,
        user_id,
        items,
        page_number=0,
        max_items=10,
        custom_formatter=None,
        extra_custom_ids="",
    ):
        self.guild_id = guild_id
        self.user_id = user_id
        self.page_number = page_number
        self.items = items
        self.max_items = max_items
        self.custom_formatter = custom_formatter
        self.extra_custom_ids = extra_custom_ids

    @property
    def embed(self):
        offset = self.page_number * self.max_items
        max_items = (
            len(self.items) if (offset + self.max_items >= len(self.items)) else offset + self.max_items
        )
        current_items = self.items[offset:max_items]

        if self.custom_formatter:
            embed = self.custom_formatter(self.page_number, current_items)
        else:
            embed = hikari.Embed(title=f"Test Pagination", description=f"Page {self.page_number}")

        return embed

    @embed.setter
    def embed(self, value):
        self._embed = value

    @property
    def components(self):
        button_row = bloxlink.rest.build_message_action_row()

        offset = self.page_number * self.max_items
        max_items = (
            len(self.items) if (offset + self.max_items >= len(self.items)) else offset + self.max_items
        )

        # Previous button
        button_row.add_interactive_button(
            hikari.ButtonStyle.SECONDARY,
            f"viewbinds:{self.user_id}:{self.page_number-1}:{self.extra_custom_ids}",
            label="\u2B9C",
            is_disabled=True if self.page_number == 0 else False,
        )

        # Next button
        button_row.add_interactive_button(
            hikari.ButtonStyle.SECONDARY,
            f"viewbinds:{self.user_id}:{self.page_number+1}:{self.extra_custom_ids}",
            label="\u2B9E",
            is_disabled=True if max_items == len(self.items) else False,
        )

        return button_row

    @components.setter
    def components(self, value):
        self._components = value


async def build_page_embed(page_components) -> hikari.Embed:
    embed = hikari.Embed()
    embed.title = "**Bloxlink Role Binds**"

    bot_user = await bloxlink.rest.fetch_my_user()
    avatar_url = bot_user.default_avatar_url if not bot_user.avatar_url else bot_user.avatar_url
    embed.set_author(name="Powered by Bloxlink", icon=avatar_url)
    embed.color = RED_COLOR
    embed.set_footer("Use /bind to make a new bind, or /unbind to delete a bind")

    if not page_components:
        page_components = (
            "You have no binds that match the options you passed. "
            "Please use `/bind` to make a new role bind, or try again with different options."
        )

    if page_components is str:
        embed.description = page_components
    else:
        if page_components["linked_group"]:
            embed.add_field("Linked Groups", "\n".join(page_components["linked_group"]))

        if page_components["group_roles"]:
            rank_map = page_components["group_roles"]
            for group in rank_map.keys():
                try:
                    embed.add_field(
                        f"{(await get_group(group)).name} ({group})", "\n".join(rank_map[group]), inline=True
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


async def build_page_components(
    guild_id: int, author_id: int, category: str, page_number: int, id_filter: str = None
) -> dict | str:
    """Generates a dictionary containing all relevant categories to generate the viewbinds embed with. Also
    generates the buttons that will be added if the bind count is over MAX_BINDS_PER_PAGE."""
    guild_data = await bloxlink.fetch_guild_data(guild_id, "binds")

    # Filter for the category.
    categories = ("group", "asset", "badge", "gamepass")
    if category not in categories:
        return (
            "Your given category option was invalid. "
            "Only `Group`, `Asset`, `Badge`, and `Gamepass` are allowed options."
        )

    if id_filter:
        id_filter = None if id_filter.lower() == "none" else id_filter

    binds = json_binds_to_guild_binds(guild_data.binds, category=category, id_filter=id_filter)
    bind_length = len(binds)

    if not bind_length:
        return ""

    output = {
        "linked_group": [],
        "group_roles": {},
        "asset": [],
        "badge": [],
        "gamepass": [],
        "button_row": None,
    }

    offset = page_number * MAX_BINDS_PER_PAGE
    max_count = bind_length if (offset + MAX_BINDS_PER_PAGE >= bind_length) else offset + MAX_BINDS_PER_PAGE
    sliced_binds = binds[offset:max_count]

    # Setup button row if necessary
    if bind_length > MAX_BINDS_PER_PAGE:
        button_row = bloxlink.rest.build_message_action_row()

        # Previous button
        button_row.add_interactive_button(
            hikari.ButtonStyle.SECONDARY,
            f"viewbinds:{author_id}:{page_number - 1}:{category}:{id_filter}",
            label="\u2B9C",
            is_disabled=True if page_number == 0 else False,
        )

        # Next button
        button_row.add_interactive_button(
            hikari.ButtonStyle.SECONDARY,
            f"viewbinds:{author_id}:{page_number + 1}:{category}:{id_filter}",
            label="\u2B9E",
            is_disabled=True if max_count == bind_length else False,
        )

        output["button_row"] = button_row

    # Used to prevent needing to get group data each iteration
    group_data = None
    for bind in sliced_binds:
        typing = bind.determine_type()

        include_id = True if typing != "group_roles" else False

        if typing == "linked_group" or typing == "group_roles":
            if not group_data or group_data.id != bind.id:
                group_data = await get_group(bind.id)

        bind_string = await bind.get_bind_string(
            guild_id=guild_id, include_id=include_id, group_data=group_data
        )

        if typing == "linked_group":
            output["linked_group"].append(bind_string)
        elif typing == "group_roles":
            select_output = output["group_roles"].get(bind.id, [])
            select_output.append(bind_string)
            output["group_roles"][bind.id] = select_output
        elif typing == "asset":
            output["asset"].append(bind_string)
        elif typing == "badge":
            output["badge"].append(bind_string)
        elif typing == "gamepass":
            output["gamepass"].append(bind_string)

    return output
