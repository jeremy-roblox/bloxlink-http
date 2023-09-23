import hikari
from hikari import Embed
from hikari.commands import CommandOption, OptionType
from hikari.errors import NotFoundError

import resources.roblox.users as users
from resources.bloxlink import instance as bloxlink
from resources.exceptions import (  # pylint: disable=import-error, no-name-in-module
    BloxlinkException,
    RobloxNotFound,
)
from resources.models import CommandContext
from resources.utils import fetch


@bloxlink.command(
    category="Administration",
    defer=True,
    options=[
        CommandOption(
            type=OptionType.STRING,
            name="target",
            description="Please specify either a Roblox username or ID",
            is_required=True,
        ),
        CommandOption(
            type=OptionType.STRING,
            name="search_type",
            description="Please specify if it is a username or ID.",
            choices=[
                hikari.CommandChoice(name="Username", value="username"),
                hikari.CommandChoice(name="ID", value="ID"),
            ],
            is_required=True,
        ),
    ],
)
class ReverseSearchCommand:
    """find Discord IDs in your server that are linked to a certain Roblox ID"""

    def __init__(self):
        self.examples = ["1", "569422833", "blox_link"]
        self.arguments = [
            {
                "prompt": "Please specify either a Roblox username or ID and the type.",
                "slash_desc": "Please specify either a Roblox username or ID and the type.",
                "name": "target",
            }
        ]
        self.category = "Administration"
        self.aliases = ["reverse-search"]
        self.slash_enabled = True

    async def __main__(self, ctx: CommandContext):
        guild = ctx.guild_id
        target = ctx.options["target"]
        search_type = ctx.options["search_type"]
        response = ctx.response

        try:
            if search_type == "username":
                json_data = await fetch(
                    "POST",
                    "https://users.roblox.com/v1/usernames/users",
                    body={"usernames": [target], "excludeBannedUsers": False},
                )

                if len(json_data[0]["data"]) == 0:
                    raise RobloxNotFound()

                roblox_id = str(json_data[0]["data"][0]["id"])
            else:
                roblox_id = target

            account = await users.get_user(roblox_id=True and roblox_id)
        except RobloxNotFound:
            raise BloxlinkException("This Roblox account doesn't exist.")
        else:
            num_documents = await bloxlink.mongo.bloxlink.users.count_documents(
                {"robloxAccounts.accounts": roblox_id}
            )

            results = []

            if num_documents > 0:
                documents = bloxlink.mongo.bloxlink.users.find({"robloxAccounts.accounts": roblox_id})

                for document in await documents.to_list(length=num_documents):
                    try:
                        user = await bloxlink.rest.fetch_member(guild, document["_id"])
                    except NotFoundError:
                        pass
                    else:
                        results.append(f"{user.mention} ({user.id})")

            embed = Embed(
                title=f"Reverse Search for {account.username}",
                description="\n".join(results) if results else "No results found.",
            )
            # embed.set_thumbnail(account.avatar)

            await ctx.response.send(embed=embed)
