from resources.bloxlink import instance as bloxlink
from resources.constants import SPLIT_CHAR, GROUP_RANK_CRITERIA
from resources.groups import get_group
from dataclasses import dataclass, field
import hikari


@dataclass(slots=True)
class EmbedPrompt:
    embed: hikari.Embed = hikari.Embed()
    components: list = field(default_factory=list)


def build_group_criteria_prompt(
    custom_id: str,
    placeholder: str = "Choose the condition for this bind.",
    embed: hikari.Embed = None,
) -> EmbedPrompt:
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
