from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext
from resources.response import Prompt, Response, PromptPageData, PromptCustomID
from resources.exceptions import RobloxNotFound
from hikari.commands import CommandOption, OptionType
from attrs import define, field
import hikari
import asyncio

# bind resource API
from resources.roblox.assets import get_asset
from resources.roblox.badges import get_badge
from resources.roblox.gamepasses import get_gamepass
from resources.roblox.groups import get_group
from resources.binds import create_bind



@define
class GroupPromptCustomID(PromptCustomID):
    group_id: int = field(converter=int)


class GroupPrompt(Prompt[GroupPromptCustomID]):
    def __init__(self, interaction: hikari.CommandInteraction, response: Response):
        super().__init__(interaction, response, self.__class__.__name__,
                         custom_id_format=GroupPromptCustomID)

    @Prompt.programmatic_page()
    async def current_binds(self, interaction: hikari.CommandInteraction | hikari.ComponentInteraction, fired_component_id: str | None):
        # TODO: get current binds

        yield PromptPageData(
            title="Current Binds",
            description="Here are the current binds for your server. Click the button below to make a new bind.",
            components=[
                PromptPageData.Component(
                    type="button",
                    label="Create a new bind",
                    component_id="new_bind",
                    is_disabled=False,
                )
            ]
        )

        # print("passed promptpagedata 1", fired_component_id, self.response.responded)

        if fired_component_id == "new_bind":
            # print("fired_component_id == new_bind")
            # print("passed promptpagedata 2", fired_component_id, self.response.responded)
            yield await self.go_to(self.create_bind_page)

    @Prompt.page(
        PromptPageData(
            title="Make a Group Bind",
            description="This menu will guide you through the process of binding a group to your server.\nPlease choose the criteria for this bind.",
            components=[
                PromptPageData.Component(
                    type="select_menu",
                    placeholder="Select a condition",
                    min_values=0,
                    max_values=1,
                    component_id="criteria_select",
                    options=[
                        PromptPageData.Component.Option(
                            name="Rank must match exactly...",
                            value="exact_match",
                        ),
                        PromptPageData.Component.Option(
                            name="Rank must be greater than or equal to...",
                            value="gte",
                        ),
                        PromptPageData.Component.Option(
                            name="Rank must be less than or equal to...",
                            value="lte",
                        ),
                        PromptPageData.Component.Option(
                            name="Rank must be within 2 rolesets...",
                            value="range",
                        ),
                        PromptPageData.Component.Option(
                            name="User must NOT be a member of this group",
                            value="not_in_group",
                        )
                    ]
                ),
            ]
        )
    )
    async def create_bind_page(self, interaction: hikari.ComponentInteraction, fired_component_id: str | None):
        match interaction.values[0]:
            case "exact_match":
                yield await self.go_to(self.bind_exact_match)

    @Prompt.programmatic_page()
    async def bind_exact_match(self, interaction: hikari.ComponentInteraction, fired_component_id: str | None):
        yield await self.response.defer()

        group_id = self.custom_id.group_id
        roblox_group = await get_group(group_id)

        yield PromptPageData(
            title="Bind Group Rank",
            description="Please select a group rank and corresponding Discord role. No existing Discord role? No problem, just click `Create new role`.",
            components=[
                PromptPageData.Component(
                    type="select_menu",
                    placeholder="Choose group rank",
                    min_values=0,
                    max_values=1,
                    component_id="group_rank",
                    options=[
                        PromptPageData.Component.Option(
                            name=roleset_name,
                            value=roleset_id,
                        ) for roleset_id, roleset_name in roblox_group.rolesets.items()
                    ]
                ),
                PromptPageData.Component(
                    type="role_select_menu",
                    placeholder="Choose a Discord role",
                    min_values=0,
                    max_values=1,
                    component_id="discord_role",
                ),
                PromptPageData.Component(
                    type="button",
                    label="Create new role",
                    component_id="new_role",
                    is_disabled=False,
                )
            ]
        )

        print(fired_component_id)
        # print("data=", await self.current_data())

        if fired_component_id == "new_role":
            await self.edit_component(
                discord_role={
                    "is_disabled": True,
                },
                new_role={
                    "label": "Use existing role",
                    "component_id": "new_role-existing_role"
                }
            )
        elif fired_component_id == "new_role-existing_role":
            await self.edit_component(
                discord_role={
                    "is_disabled": False,
                },
                new_role={
                    "label": "Create new role",
                    "component_id": "new_role"
                }
            )

        current_data = await self.current_data()

        discord_role = current_data["discord_role"]["values"][0] if current_data.get("discord_role") else None
        group_rank = current_data["group_rank"]["values"][0] if current_data.get("group_rank") else None

        print("discord role is ", discord_role)
        print("group rank is ", group_rank)

        if discord_role and group_rank:
            yield await self.go_to(self.current_binds, description=f"{discord_role}{group_rank}")

        if fired_component_id in ("group_rank", "discord_role"):
            await self.ack()

@bloxlink.command(
    category="Administration",
    defer=True,
    defer_with_ephemeral=False,
    permissions=hikari.Permissions.MANAGE_GUILD,
    dm_enabled=False,
    prompts=[GroupPrompt]
)
class BindCommand:
    """Bind Discord role(s) to Roblox entities"""

    @bloxlink.subcommand(
        options=[
            CommandOption(
                type=OptionType.INTEGER,
                name="group_id",
                description="What is your group ID?",
                is_required=True,
            ),
            CommandOption(
                type=OptionType.STRING,
                name="bind_mode",
                description="How should we merge your group with Discord?",
                choices=[
                    hikari.CommandChoice(
                        name="Bind all current and future group roles", value="entire_group"
                    ),
                    hikari.CommandChoice(name="Choose specific group roles", value="specific_roles"),
                ],
                is_required=True,
            ),
        ]
    )
    async def group(self, ctx: CommandContext):
        """Bind a group to your server"""

        group_id = ctx.options["group_id"]
        bind_mode = ctx.options["bind_mode"]

        try:
            group = await get_group(group_id)
        except RobloxNotFound:
            # Can't be ephemeral sadly bc of the defer state for the command.
            return await ctx.response.send_first(
                f"The group ID ({group_id}) you gave is either invalid or does not exist."
            )

        if bind_mode == "specific_roles":
            await ctx.response.prompt(
                GroupPrompt,
                custom_id_data={
                    "group_id": group_id,
                }
            )

        elif bind_mode == "entire_group":
            # Isn't interactive - just makes the binding and tells the user if it worked or not.
            # TODO: ask if the bot can create roles that match their group rolesets

            try:
                await create_bind(ctx.guild_id, bind_type="group", bind_id=group_id)
            except NotImplementedError:
                await ctx.response.send(
                    f"You already have a group binding for group [{group.name}](<https://www.roblox.com/groups/{group.id}/->). No changes were made."
                )
                return

            await ctx.response.send(
                f"Your group binding for group [{group.name}](https://www.roblox.com/groups/{group.id}/-) has been saved. "
                "When people join your server, they will receive a Discord role that corresponds to their group rank. "
            )
