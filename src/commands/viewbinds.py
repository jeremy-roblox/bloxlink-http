import resources.binds as binds
from resources.bloxlink import instance as bloxlink
from resources.models import CommandContext
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
        if id_option == "View binds":
            page = await self.build_page(ctx, category.lower(), page_number=0)
        else:
            page = await self.build_page(ctx, category.lower(), page_number=0, id_filter=id_option)
        if not page:
            page = "You have no binds that match the options you passed. "
            "Please use `/bind` to make a new role bind, or try again with different options."

        embed.description = page
        await ctx.response.send(embed=embed)

    # Arbitrarily choosing that 10 binds per page should be good.
    async def build_page(
        self, ctx: CommandContext, category: str, page_number: int, id_filter: str = None
    ) -> str:
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
        print(binds)
        bind_length = len(binds)

        if not bind_length:
            return ""

        output = []

        offset = page_number * MAX_BINDS_PER_PAGE
        max_count = (
            bind_length if (offset + MAX_BINDS_PER_PAGE >= bind_length) else offset + MAX_BINDS_PER_PAGE
        )
        sliced_binds = binds[offset:max_count]

        for element in sliced_binds:
            bind = element["bind"]
            bindID = bind["id"]

            nickname = element.get("nickname")
            roles = element.get("roles", [])
            remove_roles = element.get("removeRoles", [])

            # TODO: Helpers for logic such as showing names of id items + role names
            if category == "group":
                # TODO: Handle all subset group types (so guest ranks, everyone bindings, ranges, etc)
                output.append(f"Group ID: `{bindID}`; Nickname: `{nickname}`; Roles: `{roles}`\n")
            elif category == "asset":
                output.append(f"Asset ID: `{bindID}`; Nickname: `{nickname}`; Roles: `{roles}`\n")
            elif category == "badge":
                output.append(f"Badge ID: `{bindID}`; Nickname: `{nickname}`; Roles: `{roles}`\n")
            elif category == "gamepass":
                output.append(f"Gamepass ID: `{bindID}`; Nickname: `{nickname}`; Roles: `{roles}`\n")

        return "".join(output)
