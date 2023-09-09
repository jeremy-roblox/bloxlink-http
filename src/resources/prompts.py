from typing import Literal

import hikari

from resources.binds import count_binds, get_bind_desc
from resources.bloxlink import instance as bloxlink
from resources.constants import GROUP_RANK_CRITERIA
from resources.exceptions import RobloxNotFound
from resources.models import EmbedPrompt
from resources.roblox.groups import get_group
from resources.roblox.roblox_entity import create_entity


async def build_interactive_bind_base(
    bind_type: Literal["group", "asset", "gamepass", "badge"],
    bind_id: int | str,
    guild_id: int,
    author_id: int,
    disable_save: bool = False,
) -> EmbedPrompt:
    capital_type = bind_type.capitalize()
    bind_id = bind_id if isinstance(bind_id, str) else str(bind_id)

    entity = create_entity(bind_type, bind_id)
    try:
        await entity.sync()
    except RobloxNotFound:
        # Handled later.
        pass

    bind_info = str(entity) if entity else "Invalid Bind Type"
    embed = hikari.Embed(
        title=f"New {capital_type} Bind",
        description=f"> ### Binding {capital_type} - {bind_info}",
    )

    bind_count = await count_binds(guild_id, bind_id)
    embed.add_field(
        "Current Binds",
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
            hikari.ButtonStyle.SECONDARY,
            f"bind_menu:discard_button:{author_id}",
            label="Discard a bind",
            is_disabled=disable_save,
        )
        .add_interactive_button(
            hikari.ButtonStyle.PRIMARY,
            f"bind_menu:add_roles_button:{bind_type}:{bind_id}:{author_id}",
            label="Create a bind",
        )
        .add_interactive_button(
            hikari.ButtonStyle.SUCCESS,
            f"bind_menu:save_button:{bind_type}:{bind_id}:{author_id}",
            label="Save changes",
            is_disabled=disable_save,
        )
    )

    return EmbedPrompt(embed, button_menu)


def build_group_criteria_prompt(
    custom_id: str,
    author_id: str | int,
    placeholder: str = "Choose the condition for this bind.",
    embed: hikari.Embed = None,
) -> EmbedPrompt:
    """
    Builds and returns the embed and components necessary for the group bind criteria selection menu prompt.

    Args:
        custom_id (str): String that is suffixed to the base custom_id string of "bind:sel_crit"
        author_id (str | int): The original author ID, used to set the custom ID for the cancel button.
            This is not added to the custom_id parameter for the prompt that is built.
        placeholder (str): Optional placeholder text for the select menu component, will be shown to the user.
        embed (hikari.Embed): Optional base-embed. The description of the embed will be changed to match the logic for this prompt.

    Returns:
        An EmbedPrompt which consists of the embed to use, and a list of components for this prompt.
    """
    embed = hikari.Embed() if not embed else embed
    embed.title = embed.title if embed.title else "Make a Bind! - Binding Criteria Selection"
    embed.description = (
        "This menu will let you connect a Group rank to a "
        "Discord role!\n\nLets get started by choosing what ranks, or who, this binding should apply to."
    )

    criteria_menu = (
        bloxlink.rest.build_message_action_row()
        .add_text_menu(f"bind:sel_crit:{custom_id}", min_values=1, max_values=1)
        .set_placeholder(placeholder)
    )

    button_menu = bloxlink.rest.build_message_action_row().add_interactive_button(
        hikari.ButtonStyle.SECONDARY, f"bind_menu:cancel:{author_id}", label="Cancel"
    )

    for key, val in GROUP_RANK_CRITERIA.items():
        criteria_menu.add_option(val, key)

    return EmbedPrompt(embed, [criteria_menu.parent, button_menu])


async def build_roleset_selection_prompt(
    custom_id: str,
    group_id: int,
    author_id: str | int,
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
        author_id (str | int): The original author ID, used to set the custom ID for the cancel button.
            This is not added to the custom_id parameter for the prompt that is built.
        placeholder (str): Optional placeholder text for the select menu component, will be shown to the user.
        min_values (int): Optional minimum number of values that can be selected.
        max_values (int): Optional maximum number of values that can be selected.
        embed (hikari.Embed): Optional base-embed. The description of the embed will be changed to match the logic for this prompt.

    Returns:
        An EmbedPrompt which consists of the embed to use, and a list of components for this prompt.
    """
    embed = hikari.Embed() if not embed else embed
    embed.title = embed.title if embed.title else "Make a Bind! - Group Rank Selection"
    embed.description = (
        "Very good!\nNow, choose the rank"
        f"{' range ' if min_values > 1 else ' '}"
        "from your group that should receive the role given by this bind."
    )

    group = await get_group(str(group_id))

    roleset_menu = bloxlink.rest.build_message_action_row().add_text_menu(
        f"bind:sel_rank:{custom_id}", placeholder=placeholder, min_values=min_values, max_values=max_values
    )

    button_menu = bloxlink.rest.build_message_action_row().add_interactive_button(
        hikari.ButtonStyle.SECONDARY, f"bind_menu:cancel:{author_id}", label="Cancel"
    )

    for roleset_id, roleset_name in group.rolesets.items():
        if roleset_name != "Guest" and len(roleset_menu.options) < 25:
            roleset_menu.add_option(roleset_name, roleset_name)

    if max_values > len(roleset_menu.options):
        roleset_menu.set_max_values(len(roleset_menu.options))

    return EmbedPrompt(embed, [roleset_menu.parent, button_menu])


async def build_role_selection_prompt(
    custom_id: str,
    guild_id: int,
    author_id: str | int,
    original_message_id: str | int,
    placeholder: str = "Search and choose from your Discord roles!",
    min_values: int = 1,
    skip_button: bool = False,
    remove_text: bool = False,
    process_starter_text: bool = False,
    embed: hikari.Embed = None,
) -> EmbedPrompt:
    """
    Builds and returns the embed and components necessary for the Discord role selection menu prompt.

    Args:
        custom_id (str): The custom_id for the selection component,
            automatically prefixed with "bind:sel_role" or "bind:sel_rmv_role" depending on the remove_text argument.
        guild_id (int): The ID of the guild whose roles will be shown to the user to select from.
        author_id (str | int): The original author ID, used to set the custom ID for the cancel button.
            This is not added to the custom_id parameter for the prompt that is built.
        original_message_id (str | int): The original message ID, used to set the custom ID for the cancel button.
            This is not added to the custom_id parameter for the prompt that is built.
        placeholder (str): Optional placeholder text for the select menu component, will be shown to the user.
        min_values (int): Optional minimum number of values that can be selected.
        skip_button (bool): Change the Cancel button to say Skip instead when True. Also tells the user to click it to skip.
        remove_text (bool): When True, change the text to reflect the logic of selecting roles to remove, rather than add.
        process_starter_text (bool): When True, the prompt talks to the user as if they are in the middle of the process.
            Set it to False for all other bind types, since they start here (role selection, not removal).
        embed (hikari.Embed): Optional base-embed. The description of the embed will be changed to match the logic for this prompt.

    Returns:
        An EmbedPrompt which consists of the embed to use, and a list of components for this prompt.
    """
    embed = hikari.Embed() if not embed else embed
    if not embed.title:
        embed.title = (
            f"Make a Bind! - "
            f"{'Discord Role Selection' if not remove_text else 'Discord Role Removal Selection'}"
        )

    suffix = "receive" if not remove_text else "have removed"
    prefix = ""
    if not process_starter_text:
        prefix = "Good choice! Now," if not remove_text else "Finally,"
    else:
        prefix = (
            "This prompt will let you connect the asset, badge, "
            "or gamepass you are binding to a Discord role!\n\nLet's get started by"
        )

    final_suffix = (
        " in your server if they qualify for this bind."
        if not process_starter_text
        else " if they own this asset/badge/gamepass."
    )

    embed.description = (
        f"{prefix} {'choose' if not process_starter_text else 'choosing'} the role(s)"
        f" that you want people to **{suffix}** {final_suffix}"
    )

    if skip_button:
        embed.description = (
            embed.description + f"\n\n*Don't want any roles {'removed' if remove_text else 'given'}? "
            "Press the `Skip` button!*"
        )

    custom_segment = "sel_role" if not remove_text else "sel_rmv_role"
    role_menu = bloxlink.rest.build_message_action_row().add_select_menu(
        hikari.ComponentType.ROLE_SELECT_MENU,
        f"bind:{custom_segment}:{custom_id}",
        placeholder=placeholder,
        min_values=min_values if not skip_button else 0,
        max_values=25,
    )

    cancel_id = "cancel" if not skip_button else "skip"
    button_menu = bloxlink.rest.build_message_action_row().add_interactive_button(
        hikari.ButtonStyle.SECONDARY,
        f"bind_menu:{cancel_id}:{author_id}:{original_message_id}",
        label="Cancel" if not skip_button else "Skip",
    )

    return EmbedPrompt(embed=embed, components=[role_menu, button_menu])


def build_numbered_item_selection(
    custom_id: str,
    item_list: list[str],
    author_id: str | int,
    base_custom_id="bind_menu",
    placeholder: str = "Select which item should be removed.",
    label_prefix: str = "Item",
    min_values: int = 1,
    max_values: int = None,
    embed: hikari.Embed = None,
) -> EmbedPrompt:
    """
    Builds and returns the embed and components necessary for the Discord role selection menu prompt.

    Args:
        custom_id (str): The custom_id for the selection component,
            automatically prefixed with the set base_custom_id and "discard_selection".
        item_list (list[str]): List of items that can be selected from.
        author_id (str | int): The original author ID, used to set the custom ID for the cancel button.
            This is not added to the custom_id parameter for the prompt that is built.
        base_custom_id (str): Define what the prefix of the component should be. Default is "bind_menu"
        placeholder (str): Optional placeholder text for the select menu component, will be shown to the user.
        label_prefix (str): String that will be prefixed before each listed item when shown to the user.
        min_values (int): Optional minimum number of values that can be selected.
        max_values (int): Optional maximum number of values that can be selected.
        embed (hikari.Embed): Optional base-embed. The description of the embed will be changed to match the logic for this prompt.

    Returns:
        An EmbedPrompt which consists of the embed to use, and a list of components for this prompt.
    """
    embed = hikari.Embed() if not embed else embed
    embed.title = embed.title if embed.title else "Remove an unsaved binding!"
    description_list = ["Choose which binding you want removed from the list."]

    item_list = item_list[:25]

    if max_values is None:
        max_values = len(item_list)
    if min_values > max_values:
        min_values = max_values

    selection_menu = bloxlink.rest.build_message_action_row().add_text_menu(
        f"{base_custom_id}:discard_selection:{custom_id}",
        placeholder=placeholder,
        min_values=min_values,
    )

    button_menu = bloxlink.rest.build_message_action_row().add_interactive_button(
        hikari.ButtonStyle.SECONDARY, f"{base_custom_id}:cancel:{author_id}", label="Cancel"
    )

    counter = 1
    for bind in item_list:
        description_list.append(f"{counter}. {bind[2:]}")
        selection_menu.add_option(f"{label_prefix} {counter}", counter)
        counter += 1

    selection_menu.set_max_values(len(selection_menu.options))

    embed.description = "\n".join(description_list)
    return EmbedPrompt(embed=embed, components=[selection_menu.parent, button_menu])
