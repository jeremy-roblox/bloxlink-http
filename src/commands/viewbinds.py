import resources.binds as binds
from resources.bloxlink import instance as bloxlink
from resources.groups import get_group
from resources.models import CommandContext
from resources.utils import role_ids_to_names
import hikari

MAX_BINDS_PER_PAGE = 10


async def category_autocomplete_handler(interaction: hikari.AutocompleteInteraction):
    pass


async def id_autocomplete_handler(interaction: hikari.AutocompleteInteraction):
    pass


@bloxlink.command(
    category="Account",
    defer=True,
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
)
class ViewBindsCommand:
    """View your binds for your server."""

    async def __main__(self, ctx: CommandContext):
        category = ctx.options["category"]
        id_option = ctx.options["id"]

        embed = hikari.Embed()
        components = None

        # Valid categories:
        #   - Group
        #   - Asset
        #   - Badge
        #   - Gamepass

        page = None
        if id_option.lower() == "view binds":
            page = await self.build_page(ctx, category.lower(), page_number=0)
        else:
            page = await self.build_page(ctx, category.lower(), page_number=0, id_filter=id_option)

        if not page:
            page = "You have no binds that match the options you passed. "
            "Please use `/bind` to make a new role bind, or try again with different options."
        if page is str:
            embed.description = page
        else:
            # Make fields as necessary for the bind type.
            # For now just pass whatever the page output is.
            embed.description = page

        await ctx.response.send(embed=embed)

    # Arbitrarily choosing that 10 binds per page should be good.
    async def build_page(self, ctx: CommandContext, category: str, page_number: int, id_filter: str = None):
        guild_data = await bloxlink.fetch_guild_data(ctx.guild_id, "binds")

        print(guild_data.binds)
        print(guild_data.binds[0]["bind"])

        # Filter for the category.
        categories = ("group", "asset", "badge", "gamepass")
        if category not in categories:
            return (
                "Your given category option was invalid. "
                "Only `Group`, `Asset`, `Badge`, and `Gamepass` are allowed options."
            )

        binds = filter(lambda b: b["bind"]["type"] == category, guild_data.binds)
        if id_filter:
            binds = filter(lambda b: b["bind"]["id"] == id_filter, binds)

        binds = list(binds)
        bind_length = len(binds)

        if not bind_length:
            return ""

        output = {"linked_group": [], "group_roles": {}, "asset": [], "badge": [], "gamepass": []}

        offset = page_number * MAX_BINDS_PER_PAGE
        max_count = (
            bind_length if (offset + MAX_BINDS_PER_PAGE >= bind_length) else offset + MAX_BINDS_PER_PAGE
        )
        sliced_binds = binds[offset:max_count]

        group_data = None
        for element in sliced_binds:
            bind = element["bind"]
            bindID = bind["id"]

            nickname = element.get("nickname")
            roles = element.get("roles")

            # TODO: include this field in the output.
            remove_roles = element.get("removeRoles")

            role_string = await role_ids_to_names(guild_id=ctx.guild_id, roles=roles)

            if category == "group":
                if not group_data:
                    group_data = await get_group(bindID)
                elif group_data.id != bindID:
                    group_data = await get_group(bindID)

                if not roles or roles == "undefined" or roles == "null":
                    output["linked_group"].append(
                        f"**Group:** {group_data.name} ({bindID}); **Nickname:** {nickname}"
                    )
                else:
                    select_output = output["group_roles"].get(bindID, [])

                    if "min" in bind and "max" in bind:
                        select_output.append(
                            f"**Group:** {group_data.name} ({bindID}); **Nickname:** {nickname}; "
                            f"**Rank Range:** {bind['min']} to {bind['max']}; "
                            f"**Role(s):** {role_string}"
                        )

                    if "roleset" in bind:
                        select_output.append(
                            f"**Group:** {group_data.name} ({bindID}); **Nickname:** {nickname}; "
                            f"**Rank ID:** {bind['roleset']}; "
                            f"**Role(s):** {role_string}"
                        )

                    if "everyone" in bind:
                        select_output.append(
                            f"**Group:** {group_data.name} ({bindID}); **Nickname:** {nickname}; "
                            f"**Rank:** All group members; "
                            f"**Role(s):** {role_string}"
                        )

                    if "guest" in bind:
                        select_output.append(
                            f"**Group:** {group_data.name} ({bindID}); **Nickname:** {nickname}; "
                            f"**Rank** Non-group members; "
                            f"**Role(s):** {role_string}"
                        )

                    output["group_roles"][bindID] = select_output

            elif category == "asset":
                output["asset"].append(
                    f"**Asset ID:** {bindID}; **Nickname:** {nickname}`; **Role(s):** {role_string}"
                )
            elif category == "badge":
                output["badge"].append(
                    f"**Badge ID:** {bindID}; **Nickname:** {nickname}`; **Role(s):** {role_string}"
                )
            elif category == "gamepass":
                output["gamepass"].append(
                    f"**Gamepass ID:** {bindID}; **Nickname:** {nickname}`; **Role(s):** {role_string}"
                )

        return output

