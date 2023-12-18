import hikari

import resources.roblox.users as users
from resources.binds import GuildBind, get_binds
from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext
from resources.exceptions import RobloxAPIError, RobloxNotFound


async def bind_category_autocomplete(ctx: CommandContext):
    """Autocomplete for a bind category input based upon the binds the user has."""

    interaction = ctx.interaction

    guild_data = await get_binds(ctx.guild_id)
    bind_types = set(bind.type for bind in guild_data)

    yield interaction.build_response(
        [hikari.impl.AutocompleteChoiceBuilder(c.title(), c) for c in bind_types]
    )


async def bind_id_autocomplete(ctx: CommandContext):
    """Autocomplete for bind ID inputs, expects that there is an additional category option in the
    command arguments that must be set prior to this argument."""

    interaction = ctx.interaction

    choices = [
        # base option
        hikari.impl.AutocompleteChoiceBuilder("View all your bindings", "View binds")
    ]

    options = {o.name.lower(): o for o in interaction.options}

    category_option = options.get("category")
    id_option = options.get("id").value.lower() if options.get("id") else None

    # Only show more options if the category option has been set by the user.
    if category_option:
        guild_data = await get_binds(interaction.guild_id, category=category_option.value)

        if id_option:
            filtered_binds = set(bind.id for bind in guild_data if str(bind.id).startswith(id_option))
        else:
            filtered_binds = set(bind.id for bind in guild_data)

        for bind in filtered_binds:
            choices.append(hikari.impl.AutocompleteChoiceBuilder(str(bind), str(bind)))

    # Due to discord limitations, only return the first 25 choices.
    yield interaction.build_response(choices[:25])


async def roblox_lookup_autocomplete(ctx: CommandContext):
    """Return a matching roblox user from a user's input."""

    interaction = ctx.interaction

    # Makes sure that we get the correct command input in a generic way
    option = next(x for x in interaction.options if x.is_focused)

    user_input = str(option.value)
    if not user_input:
        yield interaction.build_response([])
        return

    user = None
    try:
        user = await users.get_user_from_string(user_input)
    except (RobloxNotFound, RobloxAPIError):
        pass

    result_list = []
    if user is not None:
        result_list.append(
            hikari.impl.AutocompleteChoiceBuilder(f"{user.username} ({user.id})", str(user.id))
        )

    yield interaction.build_response(result_list)
