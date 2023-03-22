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

        # match category.lower():
        #     case "group":
        #         embed, components = self.group_response(ctx, id_option)

        #     case "asset":
        #         embed, components = self.asset_response(ctx, id_option)

        #     case "badge":
        #         embed, components = self.badge_response(ctx, id_option)

        #     case "gamepass":
        #         embed, components = self.gamepass_response(ctx, id_option)

        #     case _:
        #         embed.description = (
        #             "Your given category option was invalid. "
        #             "Only `Group`, `Asset`, `Badge`, and `Gamepass` are allowed options."
        #         )
        page = await self.build_page(ctx, category.lower(), 0)
        if not page:
            page = "No binds found"

        embed.description = page
        await ctx.response.send(embed=embed)

    # This method isn't very "dry", since each method effectively makes the embed and
    # sets up any components as necessary. Might be worth reconsidering how to handle this better.

    async def group_response(self, ctx: CommandContext, id_filter: str):
        embed = hikari.Embed()
        embed.title = "Bloxlink Group Bindings"
        return

    async def asset_response(self, ctx: CommandContext, id_filter: str):
        return

    async def badge_response(self, ctx: CommandContext, id_filter: str):
        return

    async def gamepass_response(self, ctx: CommandContext, id_filter: str):
        return

    # Arbitrarily choosing that 10 binds per page should be good.
    async def build_page(
        self, ctx: CommandContext, category: str, new_page_index: int, id_filter: str = None
    ) -> str:
        guild_data = await bloxlink.fetch_guild_data(ctx.guild_id, "binds")

        print(guild_data.binds)
        print(guild_data.binds[0]["bind"])

        # Fiter for the category.
        binds = filter(lambda b: b["bind"]["type"] == category, guild_data.binds)
        if id_filter:
            binds = filter(lambda b: b["bind"]["id"] == id_filter, binds)

        binds = list(binds)
        print(binds)
        bind_length = len(binds)

        if not bind_length:
            return ""

        output = []

        offset = new_page_index * MAX_BINDS_PER_PAGE
        max_count = (
            bind_length if (offset + MAX_BINDS_PER_PAGE >= bind_length) else offset + MAX_BINDS_PER_PAGE
        )
        sliced_binds = binds[offset:max_count]

        for element in sliced_binds:
            bindID = element["bind"]["id"]
            nickname = element["nickname"]
            roles = element["roles"]

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
