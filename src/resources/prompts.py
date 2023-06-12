from resources.bloxlink import instance as bloxlink
from resources.constants import SPLIT_CHAR, GROUP_RANK_CRITERIA
from resources.exceptions import RobloxNotFound
from resources.assets import get_asset, RobloxAsset
from resources.badges import get_badge, RobloxBadge
from resources.gamepasses import get_gamepass, RobloxGamepass
from resources.groups import get_group, RobloxGroup
from resources.binds import get_bind_desc, count_binds
from dataclasses import dataclass, field
from typing import Literal
import hikari


@dataclass(slots=True)
class EmbedPrompt:
    embed: hikari.Embed = hikari.Embed()
    components: list = field(default_factory=list)


async def build_interactive_bind_base(
    bind_type: Literal["group", "asset", "gamepass", "badge"],
    bind_id: int | str,
    guild_id: int,
    author_id: int,
) -> EmbedPrompt:
    capital_type = bind_type.capitalize()
    bind_id = bind_id if isinstance(bind_id, str) else str(bind_id)

    entity = None
    try:
        if bind_type == "group":
            entity = await get_group(bind_id)
        elif bind_type == "asset":
            entity = await get_asset(bind_id)
        elif bind_type == "badge":
            entity = await get_badge(bind_id)
        elif bind_type == "gamepass":
            entity = await get_gamepass(bind_id)
    except RobloxNotFound:
        # Handled later.
        pass

    bind_info = f"{entity.name} ({entity.id})" if entity else f"*(Name not available)* {bind_id}"
    embed = hikari.Embed(
        title=f"New {capital_type} Bind",
        description=f"> ### Binding {capital_type} - {bind_info}",
    )

    bind_count = await count_binds(guild_id, bind_id)
    embed.add_field(
        f"Current Binds",
        value=(
            f"No binds exist for this {bind_type}. Click the button below to create your first bind!"
            if bind_count == 0
            else await get_bind_desc(guild_id, bind_id, bind_type)
        ),
        inline=True,
    )

    embed.add_field(name="New Binds", value="*The binds you're making will be added here!*", inline=True)

    button_menu = (
        bloxlink.rest.build_message_action_row()
        .add_interactive_button(
            hikari.ButtonStyle.PRIMARY,
            f"bind_menu:add_roles_button:{bind_type}:{bind_id}:{author_id}",
            label="Create a bind",
        )
        .add_interactive_button(
            hikari.ButtonStyle.SUCCESS,
            f"bind_menu:save_button:{bind_type}:{bind_id}:{author_id}",
            label="Save changes",
        )
    )

    return EmbedPrompt(embed, button_menu)


def build_group_criteria_prompt(
    custom_id: str,
    placeholder: str = "Choose the condition for this bind.",
    embed: hikari.Embed = None,
) -> EmbedPrompt:
    """
    Builds and returns the embed and components necessary for the group bind criteria selection menu prompt.

    Args:
        custom_id (str): The custom_id for the selection component, automatically prefixed with "bind:sel_crit"
        placeholder (str): Optional placeholder text for the select menu component, will be shown to the user.
        embed (hikari.Embed): Optional base-embed. The description of the embed will be changed to match the logic for this prompt.

    Returns:
        An EmbedPrompt which consists of the embed to use, and a list of components for this prompt.
    """
    embed = hikari.Embed() if not embed else embed
    embed.description = (
        "This menu will let you connect a Group rank to a "
        "Discord role.\nPlease choose the criteria for this bind."
    )

    criteria_menu = (
        bloxlink.rest.build_message_action_row()
        .add_text_menu(f"bind:sel_crit:{custom_id}", min_values=1, max_values=1)
        .set_placeholder(placeholder)
    )

    for key, val in GROUP_RANK_CRITERIA.items():
        criteria_menu.add_option(val, key)

    return EmbedPrompt(embed, [criteria_menu.parent])


async def build_roleset_selection_prompt(
    custom_id: str,
    group_id: int,
    placeholder: str = "Bind this Group rank",
    min_values: int = 1,
    max_values: int = 1,
    embed: hikari.Embed = None,
) -> EmbedPrompt:
    """
    Builds and returns the embed and components necessary for the group bind roleset/rank selection menu prompt.

    Args:
        custom_id (str): The custom_id for the selection component, automatically prefixed with "bind:sel_rank"
        group_id (int): The ID of the group whose roles will be shown to the user.
        placeholder (str): Optional placeholder text for the select menu component, will be shown to the user.
        min_values (int): Optional minimum number of values that can be selected.
        max_values (int): Optional maximum number of values that can be selected.
        embed (hikari.Embed): Optional base-embed. The description of the embed will be changed to match the logic for this prompt.

    Returns:
        An EmbedPrompt which consists of the embed to use, and a list of components for this prompt.
    """
    embed = hikari.Embed() if not embed else embed
    embed.description = "Very good! Now, choose the roleset from your group that should receive the role."

    group = await get_group(str(group_id))

    roleset_menu = bloxlink.rest.build_message_action_row().add_text_menu(
        f"bind:sel_rank:{custom_id}", placeholder=placeholder, min_values=min_values, max_values=max_values
    )

    for roleset_id, roleset_name in group.rolesets.items():
        if roleset_name != "Guest" and len(roleset_menu.options) < 25:
            roleset_menu.add_option(roleset_name, roleset_name)

    if max_values > len(roleset_menu.options):
        roleset_menu.set_max_values(len(roleset_menu.options))

    return EmbedPrompt(embed, [roleset_menu.parent])


async def build_role_selection_prompt(
    custom_id: str,
    guild_id: int,
    placeholder: str = "Attach this Discord role to the people who apply to this bind.",
    min_values: int = 1,
    include_none: bool = False,
    remove_text: bool = False,
    embed: hikari.Embed = None,
) -> EmbedPrompt:
    """
    Builds and returns the embed and components necessary for the Discord role selection menu prompt.

    Args:
        custom_id (str): The custom_id for the selection component,
            automatically prefixed with "bind:sel_role" or "bind:sel_rmv_role" depending on the remove_text argument.
        guild_id (int): The ID of the guild whose roles will be shown to the user to select from.
        placeholder (str): Optional placeholder text for the select menu component, will be shown to the user.
        min_values (int): Optional minimum number of values that can be selected.
        include_none (bool): Include the "[SKIP]" option in the list, allowing someone to not choose any roles.
        remove_text (bool): When True, change the text to reflect the logic of selecting roles to remove, rather than add.
        embed (hikari.Embed): Optional base-embed. The description of the embed will be changed to match the logic for this prompt.

    Returns:
        An EmbedPrompt which consists of the embed to use, and a list of components for this prompt.
    """
    embed = hikari.Embed() if not embed else embed
    suffix = "receive" if not remove_text else "have removed"
    embed.description = (
        f"Choose the role(s) from your server that you want members who qualify for this bind to {suffix}."
    )

    if include_none:
        embed.description = (
            embed.description
            + f"\nDon't want any roles {'removed' if remove_text else 'given'}? Choose the option named `[SKIP]`!"
        )

    custom_segment = "sel_role" if not remove_text else "sel_rmv_role"
    role_menu = bloxlink.rest.build_message_action_row().add_text_menu(
        f"bind:{custom_segment}:{custom_id}", placeholder=placeholder, min_values=min_values
    )

    guild_roles = await bloxlink.fetch_roles(guild_id)

    if include_none:
        role_menu.add_option("[SKIP]", "None")

    for role_id, role_data in guild_roles.items():
        if (
            role_data.name != "@everyone"
            and not role_data.bot_id
            and not role_data.integration_id
            and len(role_menu.options) < 25
        ):
            role_menu.add_option(role_data.name, f"{role_data.name}{SPLIT_CHAR}{str(role_id)}")

    role_menu.set_max_values(len(role_menu.options))

    return EmbedPrompt(embed=embed, components=[role_menu.parent])
