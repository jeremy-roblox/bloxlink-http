import hikari
from hikari.commands import CommandOption, OptionType

import resources.roblox.users as users
from resources.autocomplete import roblox_lookup_autocomplete
from resources.bloxlink import instance as bloxlink
from resources.exceptions import RobloxNotFound
from resources.commands import CommandContext


@bloxlink.command(
    category="Administration",
    defer=True,
    permissions=hikari.Permissions.MANAGE_GUILD,
    options=[
        CommandOption(
            type=OptionType.STRING,
            name="user",
            description="Please specify either a Roblox username or ID to search for.",
            is_required=True,
            autocomplete=True,
        ),
    ],
    autocomplete_handlers={
        "user": roblox_lookup_autocomplete,
    },
)
class ReverseSearchCommand:
    """Find Discord users in your server that are linked to a certain Roblox account."""

    async def __main__(self, ctx: CommandContext):
        guild = ctx.guild_id
        target = ctx.options["user"]

        account = await users.get_user_from_string(target)

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

        embed = hikari.Embed(
            title=f"Reverse Search for {account.username}",
            description="\n".join(results) if results else "No results found.",
        )
        embed.set_thumbnail(account.avatar)

        return await ctx.response.send_first(embed=embed)
