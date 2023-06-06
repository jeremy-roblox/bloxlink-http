from resources.bloxlink import instance as bloxlink
from resources.exceptions import RobloxNotFound
from resources.groups import get_group
from resources.binds import count_binds, get_bind_desc, create_bind
from resources.models import CommandContext
from resources.component_helper import (
    check_all_modified,
    set_custom_id_data,
    set_components,
    get_custom_id_data,
)
from resources.constants import SPLIT_CHAR
from resources.prompts import build_role_selection_prompt, build_roleset_selection_prompt
from hikari.commands import CommandOption, OptionType
import hikari
import re


GROUP_RANK_CRITERIA = {
    "equ": "Rank must match exactly...",
    "gte": "Rank must be greater than or equal to...",
    "lte": "Rank must be less than or equal to...",
    "rng": "Rank must be within 2 rolesets...",
    "gst": "User must NOT be a member of this group.",
    "all": "User must be a member of this group.",
}
GROUP_RANK_CRITERIA_TEXT = {
    "equ": "People with the rank",
    "gte": "People with a rank greater than or equal to",
    "lte": "People with a rank less than or equal to",
    "rng": "People with a rank between",
    "gst": "People who are not in this group",
    "all": "People who are in this group",
}


async def bind_menu_select_criteria(interaction: hikari.ComponentInteraction):
    """
    Handles the group bind criteria selection response & sets up the next prompt accordingly.

    Sets up the group rank selection prompt for all criteria except "all" and "gst", those two
    will be directed straight to role selection.
    """

    message = interaction.message

    # depending on choice, show more select menus to message
    bind_choice = interaction.values[0]

    show_roleset_menu: bool = bind_choice in ("equ", "gte", "lte", "rng")

    original_message_id, group_id = get_custom_id_data(interaction.custom_id, segment_min=3, segment_max=4)

    print("select_criteria", interaction.custom_id)
    prompt = None

    if show_roleset_menu:
        value_count = 1 if bind_choice != "rng" else 2
        prompt = await build_roleset_selection_prompt(
            f"bind:sel_rank:{original_message_id}:{bind_choice}",
            group_id,
            min_values=value_count,
            max_values=value_count,
        )

        message.embeds[0].description = (
            "Very good! Now, choose the roleset from your group " "that should receive the role."
        )
    else:
        # Skip to the role selection prompt.

        # custom_id has double colons because that is where a roleset would go (segment 4).
        prompt = await build_role_selection_prompt(
            f"bind:sel_role:{original_message_id}::{bind_choice}", interaction.guild_id
        )

        message.embeds[0].description = (
            "Finally, choose the role from your "
            "server that you want members to receive "
            "who qualify for the bind.\nNo existing role? "
            "No problem! Click the 'Create Role' button above!"
        )

    if prompt:
        await set_components(message, components=[prompt])

    return interaction.build_deferred_response(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)


async def bind_menu_select_roleset(interaction: hikari.ComponentInteraction):
    """
    Handles the selected group rank response, one or two depending on the bind condition.
    Sets up role-selection prompt.
    """
    message = interaction.message
    roleset_choices = interaction.values

    print("select_roleset", interaction.custom_id)

    original_message_id = get_custom_id_data(interaction.custom_id, 3)
    bind_choice = get_custom_id_data(interaction.custom_id, 4)
    # print("here", original_message_id)

    # show discord role menu
    roleset_str = (
        f"{roleset_choices[0]}{f'{SPLIT_CHAR}{roleset_choices[1]}' if len(roleset_choices) > 1 else ''}"
    )
    prompt = await build_role_selection_prompt(
        f"bind:sel_role:{original_message_id}:{roleset_str}:{bind_choice}",
        interaction.guild_id,
    )

    message.embeds[0].description = (
        "Choose the role from your "
        "server that you want members to receive "
        "who qualify for the bind.\nNo existing role? "
        "No problem! Click the 'Create Role' button above!"
    )

    await set_components(message, components=[prompt])

    return interaction.build_deferred_response(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)


async def bind_menu_select_role(interaction: hikari.ComponentInteraction):
    """
    Handles the role selection prompt response.

    Saves the values from the prior steps (passed via the component custom_id) and
    the selections from this prompt to the original embed description.
    """
    message = interaction.message

    print("inter vals", interaction.values)
    role_data = {}
    for item in interaction.values:
        item_data = item.split(SPLIT_CHAR)
        role_data[item_data[1]] = item_data[0]

    print("select_role", interaction.custom_id)

    custom_data = get_custom_id_data(interaction.custom_id, segment_min=3, segment_max=5)
    original_message_id = custom_data[0]

    is_group_bind = True

    roleset_data = custom_data[1]
    if SPLIT_CHAR in roleset_data:
        roleset_data = roleset_data.split(SPLIT_CHAR)
    elif roleset_data in ("asset", "badge", "gamepass"):
        is_group_bind = False

    if is_group_bind:
        bind_choice = custom_data[2]

    channel = await interaction.fetch_channel()
    original_message = await channel.fetch_message(original_message_id)

    new_description = original_message.embeds[0].description.split("\n")

    if "Pending changes:" not in new_description:
        new_description.append("Pending changes:")

    prefix = ""
    content = ""
    role_mention_str = ", ".join(f"<@&{val}>" for val in role_data.keys())

    if is_group_bind:
        prefix = GROUP_RANK_CRITERIA_TEXT.get(bind_choice, "[ERROR] No matching criteria.")
        content = ""
        if bind_choice in ("equ", "gte", "lte"):
            content = roleset_data
        elif bind_choice in ("gst", "all"):
            content = "<GROUP ID> (TBD)"
        elif bind_choice == "rng":
            min_rank = roleset_data[0]
            max_rank = roleset_data[1]

            content = f"{min_rank}** and **{max_rank}"
    else:
        prefix = "Users who own"
        content = f"{roleset_data} <ITEM/ASSET/BADGE ID> (TBD)"

    new_description.append(
        f"_{prefix} **{content}** will receive "
        f"role{'s' if len(role_data.keys()) > 1  else ''} {role_mention_str}_"
    )

    original_title = original_message.embeds[0].title
    new_title = (
        original_title if "[UNSAVED CHANGES]" in original_title else f"{original_title} [UNSAVED CHANGES]"
    )
    new_embed = hikari.Embed(title=new_title, description="\n".join(new_description))

    original_message.embeds[0] = new_embed

    await original_message.edit(embed=new_embed)
    await message.delete()

    return (
        interaction.build_response(hikari.interactions.base_interactions.ResponseType.MESSAGE_CREATE)
        .set_content(
            f"Bind added to your in-progress workflow! [Click here](https://discord.com/channels/{interaction.guild_id}/{interaction.channel_id}/{original_message_id})"
            " and click the Save button to save the bind to your server!"
        )
        .set_flags(hikari.MessageFlag.EPHEMERAL)
    )

    # await interaction.edit_initial_response(
    #     f"Bind added to your in-progress workflow! [Click here](https://discord.com/channels/{interaction.guild_id}/{interaction.channel_id}/{original_message_id})"
    #     " and click the Save button to save the bind to your server!")


async def bind_menu_add_role_button(interaction: hikari.ComponentInteraction):
    """
    Handles what will occur on the add role button press.

    Depending on the bind type, this will do different things, will only be
    applicable for group binds where specific ranks are desired, as well as
    asset, badge, and gamepass bindings.
    """
    custom_id = interaction.custom_id
    message = interaction.message

    await interaction.create_initial_response(hikari.ResponseType.DEFERRED_MESSAGE_CREATE)

    bind_type, bind_id = get_custom_id_data(custom_id, segment_min=3, segment_max=4)

    embed = hikari.Embed(
        title="Binding Role Interactive Wizard",
    )

    prompt = None

    if bind_type == "group":
        if not bind_id:
            return

        group = await get_group(bind_id)

        embed.description = (
            "This menu will let you connect a Group rank to a "
            "Discord role.\nPlease choose the criteria for this bind."
        )

        criteria_menu = (
            bloxlink.rest.build_message_action_row()
            .add_text_menu(f"bind:sel_crit:{message.id}:{bind_id}", min_values=1, max_values=1)
            .set_placeholder("Choose condition")
        )

        for key, val in GROUP_RANK_CRITERIA.items():
            criteria_menu.add_option(val, key)

        prompt = criteria_menu.parent

    elif bind_type in ("asset", "badge", "gamepass"):
        # Direct the user straight to the role selection prompt.
        prompt = await build_role_selection_prompt(
            f"bind:sel_role:{message.id}:{bind_type}", interaction.guild_id
        )
        embed.description = (
            "Choose the role from your "
            "server that you want members to receive "
            "who qualify for this bind.\nNo existing role? "
            "No problem! Click the 'Create Role' button above!"
        )

    else:
        raise NotImplementedError(f"The bind type {bind_type} is not handled yet!")

    if prompt:
        await interaction.execute(embed=embed, components=[prompt])


async def bind_menu_save_button(interaction: hikari.ComponentInteraction):
    """
    Saves the configuration found in the description of the embed to the database.
    """
    message = interaction.message
    guild_id = interaction.guild_id

    embed = message.embeds[0]
    bindings = embed.description.split("\n")[2:]

    bind_type, prompt_id = get_custom_id_data(interaction.custom_id, segment_min=3, segment_max=4)

    for bind in bindings:
        # remove underscores
        bind = bind[1:-1]

        # Get all role IDs, need to rework if adding roles to remove.
        # Probably will split on the text "roles to remove" if it exists first.
        role_ids = re.findall(r"(\d{17,})", bind)
        # Get all matches in-between double asterisks
        named_ranks = re.findall(r"\*\*(.*?)\*\*", bind)

        if bind_type == "group":
            group_bind_type = ""

            # Determine the type of binding based on the text desc.
            for criteria_type, criteria_vals in GROUP_RANK_CRITERIA_TEXT.items():
                if criteria_vals in bind:
                    group_bind_type = criteria_type
                    break

            group_data = await get_group(prompt_id)
            group_rolesets = group_data.rolesets.items()

            rank_ids = []
            for rank in named_ranks:
                for k, v in group_rolesets:
                    if v == rank:
                        rank_ids.append(k)

            if group_bind_type == "equ":
                await create_bind(
                    guild_id, bind_type, bind_id=int(prompt_id), roles=role_ids, roleset=rank_ids[0]
                )

            elif group_bind_type == "gte":
                # TODO: Consider changing so only "min" option is set.
                await create_bind(
                    guild_id, bind_type, bind_id=int(prompt_id), roles=role_ids, roleset=-abs(rank_ids[0])
                )

            elif group_bind_type == "lte":
                await create_bind(
                    guild_id, bind_type, bind_id=int(prompt_id), roles=role_ids, max=rank_ids[0]
                )

            elif group_bind_type == "rng":
                await create_bind(
                    guild_id,
                    bind_type,
                    bind_id=int(prompt_id),
                    roles=role_ids,
                    min=rank_ids[0],
                    max=rank_ids[1],
                )

            elif group_bind_type == "gst":
                await create_bind(guild_id, bind_type, bind_id=int(prompt_id), roles=role_ids, guest=True)

            elif group_bind_type == "all":
                await create_bind(guild_id, bind_type, bind_id=int(prompt_id), roles=role_ids, everyone=True)

            else:
                raise NotImplementedError("No matching group bind type was found.")

        elif bind_type in ("asset", "badge", "gamepass"):
            raise NotImplementedError("Alternative bind type found.")

    reset_embed = hikari.Embed(
        title=f"New {bind_type.capitalize()} Bind",
        description=await get_bind_desc(interaction.guild_id, int(prompt_id)),
    )
    await message.edit(embed=reset_embed)

    return (
        interaction.build_response(hikari.interactions.base_interactions.ResponseType.MESSAGE_CREATE)
        .set_content("Saved your binds")
        .set_flags(hikari.MessageFlag.EPHEMERAL)
    )


@bloxlink.command(
    category="Administration",
    defer=True,
    permissions=hikari.Permissions.MANAGE_GUILD,
    accepted_custom_ids={
        "bind_menu:add_roles_button": bind_menu_add_role_button,
        "bind:sel_rank": bind_menu_select_roleset,
        "bind:sel_role": bind_menu_select_role,
        "bind:sel_crit": bind_menu_select_criteria,
        "bind_menu:save_button": bind_menu_save_button,
    },
)
class BindCommand:
    """bind Discord role(s) to Roblox entities"""

    @bloxlink.subcommand(
        options=[
            CommandOption(
                type=OptionType.INTEGER,
                name="group_id",
                description="What is your group ID?",
                is_required=True,
            ),
            CommandOption(
                type=OptionType.STRING,
                name="bind_mode",
                description="How should we merge your group with Discord?",
                choices=[
                    hikari.CommandChoice(
                        name="Bind all current and future group roles", value="entire_group"
                    ),
                    hikari.CommandChoice(name="Choose specific group roles", value="specific_roles"),
                ],
                is_required=True,
            ),
        ]
    )
    async def group(self, ctx: CommandContext):
        """bind a group to your server"""

        group_id = ctx.options["group_id"]
        bind_mode = ctx.options["bind_mode"]

        group = await get_group(group_id)

        bind_count = await count_binds(ctx.guild_id, group.id)

        if bind_mode == "specific_roles":
            embed = hikari.Embed(
                title="New Group Bind",
                description="No binds exist for this group! Click the button below to create your first bind."
                if bind_count == 0
                else await get_bind_desc(ctx.guild_id, group.id),
            )

            button_menu = (
                bloxlink.rest.build_message_action_row()
                .add_interactive_button(
                    hikari.ButtonStyle.PRIMARY,
                    f"bind_menu:add_roles_button:group:{group_id}",
                    label="Bind new role",
                )
                .add_interactive_button(
                    hikari.ButtonStyle.SUCCESS,
                    f"bind_menu:save_button:group:{group_id}",
                    label="Save changes",
                )
            )

            await ctx.response.send(embed=embed, components=button_menu)

            # We're done here. Button clicks invoke above functions
        elif bind_mode == "entire_group":
            try:
                await create_bind(ctx.guild_id, bind_type="group", bind_id=group_id)
            except NotImplementedError:
                await ctx.response.send(
                    f'You already have a group binding for group "{group.name}" ({group_id}). No changes were made.'
                )
                return

            await ctx.response.send(
                f'Your group binding for group "{group.name}" ({group_id}) has been saved.'
            )
