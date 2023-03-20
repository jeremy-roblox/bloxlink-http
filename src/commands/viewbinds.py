import resources.binds as binds
from resources.bloxlink import instance as bloxlink
from resources.models import CommandContext
import hikari


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
        match category.lower():
            case "group":
                embed, components = self.group_response(ctx, id_option)

            case "asset":
                embed, components = self.asset_response(ctx, id_option)

            case "badge":
                embed, components = self.badge_response(ctx, id_option)

            case "gamepass":
                embed, components = self.gamepass_response(ctx, id_option)

            case _:
                embed.description = (
                    "Your given category option was invalid. "
                    "Only `Group`, `Asset`, `Badge`, and `Gamepass` are allowed options."
                )

        await ctx.response.send(embed=embed)

    # This method isn't very "dry", since each method effectively makes the embed and
    # sets up any components as necessary. Might be worth reconsidering how to handle this better.

    async def group_response(self, ctx: CommandContext, id_filter: str):
        return

    async def asset_response(self, ctx: CommandContext, id_filter: str):
        return

    async def badge_response(self, ctx: CommandContext, id_filter: str):
        return

    async def gamepass_response(self, ctx: CommandContext, id_filter: str):
        return
