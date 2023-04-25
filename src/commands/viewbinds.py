from resources.binds import GuildBind
from resources.bloxlink import instance as bloxlink
from resources.groups import get_group
from resources.models import CommandContext
from resources.constants import RED_COLOR
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
        embed.title = "**Bloxlink Role Binds**"

        bot_user = await bloxlink.rest.fetch_my_user()
        avatar_url = bot_user.default_avatar_url if not bot_user.avatar_url else bot_user.avatar_url
        embed.set_author(name="Powered by Bloxlink", icon=avatar_url)
        embed.color = RED_COLOR
        embed.set_footer("Use /bind to make a new bind, or /unbind to delete a bind")

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
            if page["linked_group"]:
                embed.add_field("Linked Groups", "\n".join(page["linked_group"]))

            if page["group_roles"]:
                rank_map = page["group_roles"]
                for group in rank_map.keys():
                    embed.add_field(f"{(await get_group(group)).name} ({group})", "\n".join(rank_map[group]))

            if page["asset"]:
                embed.add_field("Assets", "\n".join(page["asset"]))

            if page["badge"]:
                embed.add_field("Badges", "\n".join(page["badge"]))

            if page["gamepass"]:
                embed.add_field("Gamepasses", "\n".join(page["gamepass"]))

        await ctx.response.send(embed=embed)

    async def build_page(self, ctx: CommandContext, category: str, page_number: int, id_filter: str = None):
        guild_data = await bloxlink.fetch_guild_data(ctx.guild_id, "binds")

        # Filter for the category.
        categories = ("group", "asset", "badge", "gamepass")
        if category not in categories:
            return (
                "Your given category option was invalid. "
                "Only `Group`, `Asset`, `Badge`, and `Gamepass` are allowed options."
            )

        binds = [GuildBind(**bind) for bind in guild_data.binds]

        filtered_binds = filter(lambda b: b.type == category, binds)
        if id_filter:
            filtered_binds = filter(lambda b: b.id == id_filter, filtered_binds)

        binds = list(filtered_binds)
        bind_length = len(binds)

        if not bind_length:
            return ""

        output = {"linked_group": [], "group_roles": {}, "asset": [], "badge": [], "gamepass": []}

        offset = page_number * MAX_BINDS_PER_PAGE
        max_count = (
            bind_length if (offset + MAX_BINDS_PER_PAGE >= bind_length) else offset + MAX_BINDS_PER_PAGE
        )
        sliced_binds = binds[offset:max_count]

        # Used to prevent needing to get group data each iteration
        group_data = None
        for bind in sliced_binds:
            typing = bind.determine_type()

            include_id = True if typing is not "group_roles" else False

            if typing == "linked_group" or typing == "group_roles":
                if not group_data or group_data.id != bind.id:
                    group_data = await get_group(bind.id)

            bind_string = await bind.get_bind_string(
                ctx.guild_id, include_id=include_id, group_data=group_data
            )

            if typing == "linked_group":
                output["linked_group"].append(bind_string)
            elif typing == "group_roles":
                select_output = output["group_roles"].get(bind.id, [])
                select_output.append(bind_string)
                output["group_roles"][bind.id] = select_output
            elif typing == "asset":
                output["asset"].append(bind_string)
            elif typing == "badge":
                output["badge"].append(bind_string)
            elif typing == "gamepass":
                output["gamepass"].append(bind_string)

        return output
