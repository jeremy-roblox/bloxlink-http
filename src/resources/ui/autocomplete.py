from typing import TYPE_CHECKING
from bloxlink_lib import get_binds, BaseModel
from resources.api.roblox import users
from resources.exceptions import RobloxAPIError, RobloxNotFound


if TYPE_CHECKING:
    from resources.commands import CommandContext


class AutocompleteOption(BaseModel):
    """Represents an autocomplete option."""

    name: str
    value: str


async def bind_category_autocomplete(ctx: 'CommandContext'):
    """Autocomplete for a bind category input based upon the binds the user has."""

    guild_data = await get_binds(ctx.guild_id)
    bind_types = set(bind.type for bind in guild_data)

    return ctx.response.send_autocomplete([AutocompleteOption(name=x, value=x) for x in bind_types])


async def bind_id_autocomplete(ctx: 'CommandContext'):
    """Autocomplete for bind ID inputs, expects that there is an additional category option in the
    command arguments that must be set prior to this argument."""

    interaction = ctx.interaction

    choices = [
        # base option
        AutocompleteOption(name="View all your bindings", value="View binds")
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
            choices.append(AutocompleteOption(name=str(bind), value=str(bind)))

    return ctx.response.send_autocomplete(choices)


async def roblox_lookup_autocomplete(ctx: 'CommandContext'):
    """Return a matching roblox user from a user's input."""

    interaction = ctx.interaction

    # Makes sure that we get the correct command input in a generic way
    option = next(x for x in interaction.options if x.is_focused)

    user_input = str(option.value)
    if not user_input:
        return interaction.build_response([])

    user = None
    try:
        user = await users.get_user_from_string(user_input)
    except (RobloxNotFound, RobloxAPIError):
        pass

    result_list = []
    if user is not None:
        result_list.append(AutocompleteOption(f"{user.username} ({user.id})", str(user.id)))

    return ctx.response.send_autocomplete(result_list)
