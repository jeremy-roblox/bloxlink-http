import json

import hikari

from resources.autocomplete import bind_category_autocomplete, bind_id_autocomplete
from resources.binds import delete_bind, json_binds_to_guild_binds
from resources.bloxlink import instance as bloxlink
from resources.component_helper import component_author_validation, get_custom_id_data
from resources.exceptions import RobloxAPIError
from resources.models import CommandContext, GroupBind, GuildBind
from resources.pagination import Paginator

MAX_BINDS_PER_PAGE = 15


@component_author_validation(author_segment=3)
async def unbind_pagination_button(interaction: hikari.ComponentInteraction):
    message = interaction.message

    custom_id_data = get_custom_id_data(interaction.custom_id, segment_min=3)

    author_id = int(custom_id_data[0])
    page_number = int(custom_id_data[1])

    category = custom_id_data[2]
    id_filter = custom_id_data[3]

    guild_id = interaction.guild_id

    guild_data = await bloxlink.fetch_guild_data(guild_id, "binds")
    items = json_binds_to_guild_binds(guild_data.binds, category=category, id_filter=id_filter)

    paginator = Paginator(
        guild_id,
        author_id,
        source_cmd_name="unbind",
        max_items=MAX_BINDS_PER_PAGE,
        items=items,
        page_number=page_number,
        custom_formatter=_embed_formatter,
        component_generation=_component_generator,
        extra_custom_ids=f"{category}:{id_filter}",
        include_cancel_button=True,
    )

    embed = await paginator.embed
    components = await paginator.components

    await interaction.edit_message(message, embed=embed, components=components)

    return interaction.build_deferred_response(
        hikari.interactions.base_interactions.ResponseType.DEFERRED_MESSAGE_UPDATE
    )


@component_author_validation(author_segment=3, defer=False)
async def unbind_discard_binding(interaction: hikari.ComponentInteraction):
    """Handles the removal of a binding from the list."""

    await interaction.create_initial_response(
        hikari.ResponseType.DEFERRED_MESSAGE_CREATE, flags=hikari.MessageFlag.EPHEMERAL
    )

    author_id, category, id_option = get_custom_id_data(interaction.custom_id, segment_min=3, segment_max=6)

    for item in interaction.values:
        split = item.split(":", maxsplit=1)

        bind_id = int(split[0])
        bind_data = json.loads(split[1]) if len(split) > 1 else {}

        await delete_bind(interaction.guild_id, category, bind_id, **bind_data)

    # Reset the prompt to page 0.
    guild_id = interaction.guild_id
    guild_data = await bloxlink.fetch_guild_data(guild_id, "binds")
    items = json_binds_to_guild_binds(guild_data.binds, category=category, id_filter=id_option)

    paginator = Paginator(
        guild_id,
        author_id,
        source_cmd_name="unbind",
        max_items=MAX_BINDS_PER_PAGE,
        items=items,
        custom_formatter=_embed_formatter,
        component_generation=_component_generator,
        extra_custom_ids=f"{category}:{id_option}",
        include_cancel_button=True,
    )

    await bloxlink.rest.edit_message(
        interaction.channel_id,
        interaction.message.id,
        embed=(await paginator.embed),
        components=(await paginator.components),
    )
    await interaction.edit_initial_response("Your chosen bindings have been removed.")

    return interaction.build_deferred_response(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)


@component_author_validation(author_segment=3, defer=False)
async def unbind_cancel_button(interaction: hikari.ComponentInteraction):
    if interaction.message.flags & hikari.MessageFlag.EPHEMERAL == hikari.MessageFlag.EPHEMERAL:
        await interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_UPDATE, content="Prompt cancelled.", components=[], embeds=[]
        )

        return interaction.build_response(hikari.ResponseType.MESSAGE_UPDATE)
    else:
        await bloxlink.rest.delete_message(interaction.channel_id, interaction.message)

    return (
        interaction.build_response(hikari.ResponseType.MESSAGE_CREATE)
        .set_content("Prompt cancelled.")
        .set_flags(hikari.MessageFlag.EPHEMERAL)
    )


@bloxlink.command(
    category="Administration",
    defer=True,
    permissions=hikari.Permissions.MANAGE_GUILD,
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
        "unbind:page": unbind_pagination_button,
        "unbind:sel_discard": unbind_discard_binding,
        "unbind:cancel": unbind_cancel_button,
    },
    autocomplete_handlers={
        "category": bind_category_autocomplete,
        "id": bind_id_autocomplete,
    },
    dm_enabled=False,
)
class UnbindCommand:
    """Delete some binds from your server"""

    async def __main__(self, ctx: CommandContext):
        category = ctx.options["category"]
        id_option = ctx.options["id"]

        guild_id = ctx.guild_id
        user_id = ctx.user.id

        guild_data = await bloxlink.fetch_guild_data(guild_id, "binds")
        items = json_binds_to_guild_binds(guild_data.binds, category=category, id_filter=id_option)

        paginator = Paginator(
            guild_id,
            user_id,
            source_cmd_name="unbind",
            max_items=MAX_BINDS_PER_PAGE,
            items=items,
            custom_formatter=_embed_formatter,
            component_generation=_component_generator,
            extra_custom_ids=f"{category}:{id_option}",
            include_cancel_button=True,
        )

        embed = await paginator.embed
        components = await paginator.components

        await ctx.response.send(embed=embed, components=components)


async def _embed_formatter(page_number: int, current_items: list, guild_id: int | str, max_pages: int):
    embed = hikari.Embed(title="Remove a Binding")

    if len(current_items) == 0:
        embed.description = (
            "> You have no binds that match the options you passed. "
            "Use `/bind` to make a new binding, or try again with different options."
        )
        return embed

    embed.description = "**Select which bind(s) you want to remove from the menu below!**"

    if max_pages != 1:
        embed.description += (
            "\n\n> Don't see the binding that you're looking for? "
            "Use the buttons below to have the menu scroll to a new page."
        )

    embed.set_footer(f"Page {page_number + 1}/{max_pages}")
    return embed


async def _component_generator(items: list, user_id: int | str, extra_custom_ids: str):
    selection_menu = bloxlink.rest.build_message_action_row().add_text_menu(
        f"unbind:sel_discard:{user_id}:{extra_custom_ids}",
        placeholder="Select which bind should be removed.",
        min_values=1,
    )

    if not items:
        selection_menu.set_is_disabled(True)
        selection_menu.add_option("No bindings to remove", "N/A")
        selection_menu.set_placeholder("You have no bindings to remove. Use /bind to make some first!")
        return selection_menu.parent

    for bind in items:
        bind: GuildBind
        bind_type = bind.type

        if not bind.entity.synced:
            try:
                await bind.entity.sync()
            except RobloxAPIError:
                pass

        bind_name = str(bind.entity).replace("**", "")

        if bind.type != "group":
            selection_menu.add_option(bind_name, str(bind.id))
            continue

        bind: GroupBind
        bind_type = bind.subtype

        if bind_type == "linked_group":
            selection_menu.add_option(
                bind_name,
                str(bind.id),
                description="This is a linked group binding.",
            )

        elif bind_type == "group_roles":
            group = bind.entity
            # Map with only relevant bind data, used for bind deletion from the db.
            bind_data = {}

            label = ""

            if bind.everyone:
                bind_data["everyone"] = bind.everyone
                label = "All group members"

            elif bind.guest:
                bind_data["guest"] = bind.guest
                label = "Non-group members"

            elif bind.min and bind.max:
                bind_data["min"] = bind.min
                bind_data["max"] = bind.max

                min_str = group.roleset_name_string(bind.min, bold_name=False)
                max_str = group.roleset_name_string(bind.max, bold_name=False)

                label = f"Ranks {min_str} to {max_str}"

            elif bind.min:
                bind_data["min"] = bind.min

                min_str = group.roleset_name_string(bind.min, bold_name=False)
                label = f"Rank {min_str} or above"

            elif bind.max:
                bind_data["max"] = bind.max

                max_str = group.roleset_name_string(bind.max, bold_name=False)
                label = f"Rank {max_str} or below"

            elif bind.roleset:
                bind_data["roleset"] = bind.roleset

                name = group.roleset_name_string(abs(bind.roleset), bold_name=False)
                label = f"Rank {name} or above" if bind.roleset < 0 else f"Rank {name}"

            selection_menu.add_option(
                label[:100],
                f"{str(bind.id)}:{json.dumps(bind_data, separators=(',', ':'))}",
                description=f"Group: {bind_name}",
            )

    selection_menu.set_max_values(len(selection_menu.options))

    return selection_menu.parent
