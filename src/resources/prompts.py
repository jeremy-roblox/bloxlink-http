from resources.bloxlink import instance as bloxlink
from resources.constants import SPLIT_CHAR
from resources.groups import get_group
import hikari


async def build_roleset_selection_prompt(
    custom_id: str,
    group_id: int,
    placeholder: str = "Bind this Group rank",
    min_values: int = 1,
    max_values: int = 1,
) -> hikari.api.MessageActionRowBuilder:
    group = await get_group(str(group_id))

    roleset_menu = bloxlink.rest.build_message_action_row().add_text_menu(
        custom_id, placeholder=placeholder, min_values=min_values, max_values=max_values
    )

    for roleset_id, roleset_name in group.rolesets.items():
        if roleset_name != "Guest" and len(roleset_menu.options) < 25:
            roleset_menu.add_option(roleset_name, roleset_name)

    return roleset_menu.parent


async def build_role_selection_prompt(
    custom_id: str,
    guild_id: int,
    placeholder: str = "Attach this Discord role to the people who apply to this bind.",
    min_values: int = 1,
    include_none: bool = False,
) -> hikari.api.MessageActionRowBuilder:
    role_menu = bloxlink.rest.build_message_action_row().add_text_menu(
        custom_id, placeholder=placeholder, min_values=min_values
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

    return role_menu.parent
