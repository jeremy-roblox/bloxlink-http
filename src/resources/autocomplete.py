import hikari

import resources.roblox.users as users
from resources.bloxlink import instance as bloxlink
from resources.exceptions import RobloxAPIError, RobloxNotFound
from resources.models import GuildBind


async def bind_category_autocomplete(interaction: hikari.AutocompleteInteraction):
    """Autocomplete for a bind category input based upon the binds the user has."""

    guild_data = await bloxlink.fetch_guild_data(interaction.guild_id, "binds")

    bind_types = set(bind["bind"]["type"] for bind in guild_data.binds)

    return interaction.build_response(
        [hikari.impl.AutocompleteChoiceBuilder(c.title(), c) for c in bind_types]
    )


async def bind_id_autocomplete(interaction: hikari.AutocompleteInteraction):
    """Autocomplete for bind ID inputs, expects that there is an additional category option in the
    command arguments that must be set prior to this argument."""

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


async def roblox_lookup_autocomplete(interaction: hikari.AutocompleteInteraction):
    """Return a matching roblox user from a user's input."""

    # Makes sure that we get the correct command input in a generic way
    option = next(x for x in interaction.options if x.is_focused)

    user_input = str(option.value)
    if not user_input:
        return interaction.build_response([])

    user = None

    if user_input.isdigit():
        try:
            user = await users.get_user(roblox_id=user_input)
        except (RobloxNotFound, RobloxAPIError):
            pass

    # Fallback to parse input as a username if the input was not a valid id.
    if user is None:
        try:
            user = await users.get_user(roblox_username=user_input)
        except (RobloxNotFound, RobloxAPIError):
            pass

    result_list = []
    if user is not None:
        result_list.append(
            hikari.impl.AutocompleteChoiceBuilder(f"{user.username} ({user.id})", str(user.id))
        )

    return interaction.build_response(result_list)
