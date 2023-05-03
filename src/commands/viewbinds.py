from resources.binds import GuildBind
from resources.bloxlink import instance as bloxlink
from resources.groups import get_group
from resources.models import CommandContext
from resources.constants import RED_COLOR
from datetime import datetime
import hikari


MAX_BINDS_PER_PAGE = 10


async def viewbinds_category_autocomplete(interaction: hikari.AutocompleteInteraction):
    guild_data = await bloxlink.fetch_guild_data(interaction.guild_id, "binds")

    # Bools used to prevent duplicates.
    group = asset = badge = gamepass = False

    choices = []
    binds = [GuildBind(**bind) for bind in guild_data.binds]

    # Get user input in a guaranteed manner.
    user_input = ""
    for option in interaction.options:
        if option.name == "category":
            user_input = option.value

    for bind in binds:
        bind_type = bind.type

        if bind_type == "asset" and not asset and "asset".startswith(user_input):
            choices.append(hikari.impl.AutocompleteChoiceBuilder("Asset", "Asset"))
            asset = True
        elif bind_type == "badge" and not badge and "badge".startswith(user_input):
            choices.append(hikari.impl.AutocompleteChoiceBuilder("Badge", "Badge"))
            badge = True
        elif bind_type == "gamepass" and not gamepass and "gamepass".startswith(user_input):
            choices.append(hikari.impl.AutocompleteChoiceBuilder("Gamepass", "Gamepass"))
            gamepass = True
        elif bind_type == "group" and not group and "group".startswith(user_input):
            choices.append(hikari.impl.AutocompleteChoiceBuilder("Group", "Group"))
            group = True

    return interaction.build_response(choices)


async def viewbinds_id_autocomplete(interaction: hikari.AutocompleteInteraction):
    category_option = None
    id_option = None

    base_option = hikari.impl.AutocompleteChoiceBuilder("View all your bindings", "View binds")
    # Always include the option to view all bindings.
    choices = [base_option]

    for option in interaction.options:
        if option.name == "category":
            category_option = option
        elif option.name == "id":
            id_option = option

    # Only show more options if the category option has been set by the user.
    if category_option:
        guild_data = await bloxlink.fetch_guild_data(interaction.guild_id, "binds")

        # Conversion to GuildBind is because it's easier to get the typing for filtering.
        binds = [GuildBind(**bind) for bind in guild_data.binds]
        filtered_binds = filter(lambda b: b.type.lower() == category_option.value.lower(), binds)

        user_input = id_option.value.lower()

        # Remove duplicate ids
        id_list = [*set([bind.id for bind in filtered_binds])]

        # Filter id list with user input
        filtered_binds = filter(lambda b: str(b).startswith(user_input), id_list)

        for bind in filtered_binds:
            choices.append(hikari.impl.AutocompleteChoiceBuilder(str(bind), str(bind)))

    # Due to discord limitations, only return the first 25 choices.
    return interaction.build_response(choices[:25])


async def viewbinds_button(interaction: hikari.ComponentInteraction):
    """Handles the pagination buttons for viewbinds. Since the custom_id includes the next page,
    we only need one method to handle both buttons."""
    custom_id_data = interaction.custom_id.split(":")

    author_id = custom_id_data[1]
    page_number = custom_id_data[2]
    category = custom_id_data[3]
    id_filter = custom_id_data[4]

    # 15 minute timeout on prompts. Woo stateless.
    # Could also just edit the message to remove the buttons?
    time_diff = datetime.utcnow() - interaction.message.timestamp.replace(tzinfo=None)
    if (time_diff.seconds / 60) >= 15:
        return (
            interaction.build_response(hikari.ResponseType.MESSAGE_CREATE)
            .set_content(
                "This prompt is quite old, try running the command again and using that prompt instead."
            )
            .set_flags(hikari.MessageFlag.EPHEMERAL)
        )

    if str(interaction.member.id) != author_id:
        # Could just silently fail too... Can't defer before here or else the eph response
        # fail to show up.
        return (
            interaction.build_response(hikari.ResponseType.MESSAGE_CREATE)
            .set_content("You are not the person who ran this command!")
            .set_flags(hikari.MessageFlag.EPHEMERAL)
        )
    else:
        await interaction.create_initial_response(
            hikari.ResponseType.DEFERRED_MESSAGE_UPDATE, flags=hikari.MessageFlag.EPHEMERAL
        )

    page = await build_page_components(
        interaction.guild_id, int(author_id), category, int(page_number), id_filter
    )
    embed = await build_page_embed(page)

    # Update the embed.
    await interaction.edit_message(interaction.message, embed=embed, components=[page["button_row"]])

    # Return an empty message_update response so that way Hikari doesn't complain about nothing being returned.
    # Can be omitted, just clogs up the logs otherwise. Might be worthwhile seeing if there is a "proper" way
    # to edit the embed by returning from this function.
    return interaction.build_response(hikari.ResponseType.MESSAGE_UPDATE)


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
    """View your binds for your server."""

    async def __main__(self, ctx: CommandContext):
        category = ctx.options["category"]
        id_option = ctx.options["id"]

        page = None
        if id_option.lower() == "view binds":
            page = await build_page_components(
                ctx.guild_id, ctx.member.user.id, category.lower(), page_number=0
            )
        else:
            page = await build_page_components(
                ctx.guild_id, ctx.member.user.id, category.lower(), page_number=0, id_filter=id_option
            )

        embed = await build_page_embed(page)
        button_row = page["button_row"]
        await ctx.response.send(embed=embed, components=button_row)


async def build_page_embed(page_components) -> hikari.Embed:
    embed = hikari.Embed()
    embed.title = "**Bloxlink Role Binds**"

    bot_user = await bloxlink.rest.fetch_my_user()
    avatar_url = bot_user.default_avatar_url if not bot_user.avatar_url else bot_user.avatar_url
    embed.set_author(name="Powered by Bloxlink", icon=avatar_url)
    embed.color = RED_COLOR
    embed.set_footer("Use /bind to make a new bind, or /unbind to delete a bind")

    if not page_components:
        page_components = "You have no binds that match the options you passed. "
        "Please use `/bind` to make a new role bind, or try again with different options."

    if page_components is str:
        embed.description = page_components
    else:
        if page_components["linked_group"]:
            embed.add_field("Linked Groups", "\n".join(page_components["linked_group"]))

        if page_components["group_roles"]:
            rank_map = page_components["group_roles"]
            for group in rank_map.keys():
                embed.add_field(f"{(await get_group(group)).name} ({group})", "\n".join(rank_map[group]))

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

    binds = [GuildBind(**bind) for bind in guild_data.binds]

    filtered_binds = filter(lambda b: b.type == category, binds)

    if id_filter and str(id_filter).lower() != "none":
        filtered_binds = filter(lambda b: str(b.id) == id_filter, filtered_binds)

    binds = list(filtered_binds)
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
            label="<<",
            is_disabled=True if page_number == 0 else False,
        )

        # Next button
        button_row.add_interactive_button(
            hikari.ButtonStyle.SECONDARY,
            f"viewbinds:{author_id}:{page_number + 1}:{category}:{id_filter}",
            label=">>",
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
