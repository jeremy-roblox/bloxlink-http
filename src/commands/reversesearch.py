import hikari
from hikari import Embed
from hikari.commands import CommandOption, OptionType

import resources.roblox.users as users
from resources.bloxlink import instance as bloxlink
from resources.exceptions import RobloxNotFound
from resources.models import CommandContext


@bloxlink.command(
    category="Administration",
    defer=True,
    options=[
        CommandOption(
            type=OptionType.STRING,
            name="user",
            description="Please specify either a Roblox username or ID to search for.",
            is_required=True,
        ),
        CommandOption(
            type=OptionType.STRING,
            name="type",
            description="Are you searching for a username or a roblox ID?",
            choices=[
                hikari.CommandChoice(name="Username", value="username"),
                hikari.CommandChoice(name="ID", value="ID"),
            ],
            is_required=True,
        ),
    ],
)
class ReverseSearchCommand:
    """Find Discord users in your server that are linked to a certain Roblox account."""

    async def __main__(self, ctx: CommandContext):
        guild = ctx.guild_id
        target = ctx.options["user"]
        search_type = ctx.options["type"]

        username = None if search_type != "username" else target
        roblox_id = None if search_type != "ID" else target

        if not target.isdigit() and search_type == "ID":
            await ctx.response.send(
                "The input you gave is not an ID! Try again with the username option chosen instead."
            )
            return

        try:
            account = await users.get_user(roblox_username=username, roblox_id=roblox_id)
        except RobloxNotFound as exc:
            raise RobloxNotFound(
                "The Roblox user you were searching for does not exist! "
                f"Please check the {search_type} and try again!"
            ) from exc

        if account.id is None or account.username is None:
            raise RobloxNotFound("The Roblox user you were searching for does not exist.")

        results = []

        id_list = await bloxlink.reverse_lookup(account.id)
        for user_id in id_list:
            user = await bloxlink.fetch_discord_member(guild, user_id, "id")

            if user is None:
                continue

            if isinstance(user, hikari.Member):
                results.append(f"{user.mention} ({user.id})")

            elif isinstance(user, dict):
                user_id = user["data"]["id"]
                results.append(f"<@{user_id}> ({user_id})")

        embed = Embed(
            title=f"Reverse Search for {account.username}",
            description="\n".join(results) if results else "No results found.",
        )
        embed.set_thumbnail(account.avatar)

        await ctx.response.send(embed=embed)
