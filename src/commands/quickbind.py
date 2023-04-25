from resources.bloxlink import instance as bloxlink


@bloxlink.command()
class QuickBindCommand:
    """insert some fake binds"""

    async def __main__(self, ctx):
        guild_id = ctx.guild_id

        binds = [
            {
                "roles": ["1046988399208321024"],
                # "removeRoles": ["1046308369151041556", "1234567890123"],
                "nickname": "{roblox-name}",
                "bind": {
                    "type": "group",
                    "id": 1
                }
            },
            {
                "roles": ["1046988399208321024"],
                # "removeRoles": ["1046308369151041556", "1234567890123"],
                "nickname": "{roblox-name}",
                "bind": {
                    "type": "group",
                    "id": 2
                }
            },
            {
                "roles": ["1234567890123"],
                "removeRoles": ["1234567890123", "1234567890123"],
                "nickname": "{roblox-name}",
                "bind": {
                    "type": "group",
                    "id": 1,
                    "min": 1,
                    "max": 5
                }
            },
            # {
            #     "roles": ["1234567890123"],
            #     "removeRoles": ["1234567890123", "1234567890123"],
            #     "nickname": "{roblox-name}",
            #     "bind": {
            #         "type": "group",
            #         "id": 2,
            #         "roleset": -200,
            #     }
            # },
            # {
            #     "roles": ["1234567890123"],
            #     "removeRoles": ["1234567890123", "1234567890123"],
            #     "nickname": "{roblox-name}",
            #     "bind": {
            #         "type": "group",
            #         "id": 2,
            #         "everyone": True,
            #     }
            # },
            # {
            #     "roles": ["1234567890123"],
            #     "removeRoles": ["1234567890123", "1234567890123"],
            #     "nickname": "{roblox-name}",
            #     "bind": {
            #         "type": "group",
            #         "id": 2,
            #         "guest": True,
            #     }
            # }
        ]

        await bloxlink.update_guild_data(guild_id, binds=binds)

        await ctx.response.send("added binds")
