import json

import hikari

from bloxlink_lib import VALID_BIND_TYPES, GuildBind
from resources.ui.autocomplete import bind_category_autocomplete, bind_id_autocomplete
from resources.ui.components import component_author_validation, TextSelectMenu
from resources.binds import delete_bind, get_binds, generate_binds_embed
from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.exceptions import RobloxAPIError
from resources.pagination import Paginator, PaginatorCustomID

MAX_BINDS_PER_PAGE = 10


class UnbindCustomID(PaginatorCustomID):
    """Represents a custom ID for /unbind command."""

    category: VALID_BIND_TYPES
    id: int | None = None


@component_author_validation(parse_into=UnbindCustomID)
async def unbind_pagination_button(ctx: CommandContext, custom_id: UnbindCustomID):
    """Handle the left and right buttons for pagination."""

    interaction = ctx.interaction

    author_id = custom_id.user_id
    page_number = custom_id.page_number

    category = custom_id.category
    id_filter = custom_id.id

    guild_id = interaction.guild_id

    bindings = await get_binds(guild_id, category=category, bind_id=id_filter)

    paginator = Paginator(
        guild_id,
        author_id,
        max_items=MAX_BINDS_PER_PAGE,
        items=bindings,
        page_number=page_number,
        custom_formatter=embed_formatter,
        component_generation=component_generator,
        custom_id_format=UnbindCustomID(
            command_name="unbind",
            user_id=author_id,
            category=category,
            id=id_filter),
        include_cancel_button=True,
    )

    embed = await paginator.embed
    components = await paginator.components

    await ctx.response.send(embed=embed, components=components, edit_original=True) # TODO: send_first is not working


@component_author_validation(parse_into=UnbindCustomID, defer=False)
async def unbind_discard_binding(ctx: CommandContext, custom_id: UnbindCustomID):
    """Handles the removal of a binding from the list."""

    interaction = ctx.interaction

    author_id = custom_id.user_id
    page_number = custom_id.page_number

    category = custom_id.category
    id_filter = custom_id.id

    # await interaction.create_initial_response(
    #     hikari.ResponseType.DEFERRED_MESSAGE_CREATE, flags=hikari.MessageFlag.EPHEMERAL
    # )

    # for item in interaction.values:
    #     split = item.split(":", maxsplit=1)

    #     bind_id = int(split[0])
    #     bind_data = json.loads(split[1]) if len(split) > 1 else {}

    #     await delete_bind(interaction.guild_id, category, bind_id, **bind_data)

    # # Reset the prompt to page 0.
    # guild_id = interaction.guild_id
    # bindings = await get_binds(guild_id, category=category, bind_id=id_option)

    # paginator = Paginator(
    #     guild_id,
    #     author_id,
    #     command_name="unbind",
    #     max_items=MAX_BINDS_PER_PAGE,
    #     items=bindings,
    #     custom_formatter=embed_formatter,
    #     component_generation=component_generator,
    #     custom_id_format=UnbindCustomID(
    #         command_name="unbind",
    #         user_id=author_id,
    #         category=category,
    #         id=id_filter),
    #     include_cancel_button=True,
    # )

    # await bloxlink.rest.edit_message(
    #     interaction.channel_id,
    #     interaction.message.id,
    #     embed=(await paginator.embed),
    #     components=(await paginator.components),
    # )
    # await interaction.edit_initial_response("Your chosen bindings have been removed.")

    # return interaction.build_deferred_response(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)


@component_author_validation(parse_into=UnbindCustomID, defer=False)
async def unbind_cancel_button(ctx: CommandContext, _custom_id: UnbindCustomID):
    """Handle the cancel button press."""

    interaction = ctx.interaction

    if interaction.message.flags & hikari.MessageFlag.EPHEMERAL == hikari.MessageFlag.EPHEMERAL:
        await interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_UPDATE, content="Prompt cancelled.", components=[], embeds=[]
        )

        return interaction.build_response(hikari.ResponseType.MESSAGE_UPDATE)

    await bloxlink.rest.delete_message(interaction.channel_id, interaction.message)

    return (
        interaction.build_response(hikari.ResponseType.MESSAGE_CREATE)
        .set_content("Prompt cancelled.")
        .set_flags(hikari.MessageFlag.EPHEMERAL)
    )


def viewbinds_item_filter(items: list[GuildBind]):
    """Sorts the given binds."""

    return sorted(items, key=lambda item: item.criteria.id)


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
class UnbindCommand(GenericCommand):
    """Delete some binds from your server"""

    async def __main__(self, ctx: CommandContext):
        category = ctx.options["category"]
        id_option = ctx.options["id"] if ctx.options["id"] != "view_binds" else None

        guild_id = ctx.guild_id
        user_id = ctx.user.id

        guild_binds = await get_binds(guild_id, bind_id=int(id_option) if id_option and id_option.isdigit() else None, category=category)

        paginator = Paginator(
            guild_id,
            user_id,
            max_items=MAX_BINDS_PER_PAGE,
            items=guild_binds,
            custom_formatter=embed_formatter,
            component_generation=component_generator,
            custom_id_format=UnbindCustomID(
                command_name="unbind",
                user_id=user_id,
                category=category,
                id=id_option),
            include_cancel_button=True,
            item_filter=viewbinds_item_filter
        )

        embed = await paginator.embed
        components = await paginator.components

        await ctx.response.send(embed=embed, components=components)


async def embed_formatter(page_number: int, items: list[GuildBind], _guild_id: str | int, max_pages: int):
    """Generates the embed for the page.

    Args:
        page_number (int): The page number of the page to build.
        items (list): The bindings to show on the page.
        _guild_id (str | int): Unused, the ID of the guild that the command was run in.
        max_pages (int): The page number of the last page that can be built.

    Returns:
        hikari.Embed: The formatted embed.
    """

    embed = hikari.Embed(title="Remove a Binding")

    if not items:
        embed.description = (
            "> You have no binds that match the options you passed. "
            "Use `/bind` to make a new binding, or try again with different options."
        )
        return embed

    embed.description = "Select which bind(s) you want to remove from the menu below!"

    if max_pages > 1:
        embed.description += (
            "\n\n> Don't see the binding that you're looking for? "
            "Use the buttons below to have the menu scroll to a new page."
        )

    await generate_binds_embed(items, embed)

    embed.set_footer(f"Page {page_number + 1}/{max_pages}")

    return embed


async def component_generator(items: list[GuildBind], custom_id: UnbindCustomID):
    """Generate the components for the paginator."""

    text_menu = TextSelectMenu(
        custom_id=UnbindCustomID(
            command_name="unbind",
            user_id=custom_id.user_id,
            category=custom_id.category,
            id=custom_id.id,
            section="sel_discard"
        ),
        placeholder="Select which bind should be removed",
        min_values=1,
        max_values=len(items)
    )

    if not items:
        return None

    for i, bind in enumerate(items):
        bind_type = bind.type.title()
        bind_name = str(bind.entity).replace("**", "")

        try:
            await bind.entity.sync()
        except RobloxAPIError:
            pass

        text_menu.options.append(
            TextSelectMenu.Option(
                label=f"{bind.description_prefix} {bind.description_content}"[:100],
                value=f"{bind.criteria.id}:{i}",
                description=f"{bind_type}: {bind_name}",
            )
        )

    return [text_menu]
