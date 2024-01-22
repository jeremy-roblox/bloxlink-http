from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext, GenericCommand
from resources.components import Button, Separator, RoleSelectMenu, TextSelectMenu
import hikari


@bloxlink.command(
    category="Miscellaneous",
)
class PingCommand(GenericCommand):
    """check if the bot is alive"""

    async def __main__(self, ctx: CommandContext):
        return await ctx.response.send_first("pong", components=[
            Button(
                label="test",
                custom_id="test1"
            ),
            RoleSelectMenu(
                placeholder="Choose a Discord role",
                min_values=0,
                max_values=1,
                custom_id="discord_role",
            ),
            TextSelectMenu(
                    placeholder="Select a condition",
                    min_values=0,
                    max_values=1,
                    custom_id="criteria_select",
                    options=[
                        TextSelectMenu.Option(
                            label="Rank must match exactly...",
                            value="exact_match",
                        ),
                        TextSelectMenu.Option(
                            label="Rank must be greater than or equal to...",
                            value="gte",
                        ),
                        TextSelectMenu.Option(
                            label="Rank must be less than or equal to...",
                            value="lte",
                        ),
                        TextSelectMenu.Option(
                            label="Rank must be between two rolesets...",
                            value="range",
                        ),
                        TextSelectMenu.Option(
                            label="User MUST be a member of this group",
                            value="in_group",
                        ),
                        TextSelectMenu.Option(
                            label="User must NOT be a member of this group",
                            value="not_in_group",
                        ),
                    ],
                ),
            # Separator(),
            # Button(
            #     label="test",
            #     custom_id="test2"
            # ),
        ])
