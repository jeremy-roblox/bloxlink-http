import hikari
from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext
from resources.response import Prompt, PromptPageData, Response





class SetupPrompt(Prompt):
    def __init__(self, interaction: hikari.CommandInteraction, response: Response):
        super().__init__(
            interaction,
            response,
            self.__class__.__name__
        )

    @Prompt.page(
        PromptPageData(
            title="Setup Bloxlink",
            description=("Thank you for choosing Bloxlink, the most popular Roblox-Discord integration! In a few simple prompts, we'll configure Bloxlink for your server."
                         ""
            ),
            components=[
                PromptPageData.Component(
                    type="button",
                    label="Next",
                    component_id="next",
                    is_disabled=False,
                ),
                PromptPageData.Component(
                    type="button",
                    label="Cancel",
                    component_id="cancel",
                    is_disabled=False,
                    style=hikari.ButtonStyle.SECONDARY
                ),
            ]
        )
    )
    async def intro_page(self, interaction: hikari.CommandInteraction | hikari.ComponentInteraction, fired_component_id: str | None):
        match fired_component_id:
            case "next":
                return await self.next()
            case "cancel":
                return await self.finish()

    @Prompt.page(
        PromptPageData(
            title="Setup Bloxlink",
            description=("Should your members be given a different nickname? Please note that by default, Bloxlink will name users as: `Display Name (@Roblox Username)`.\n\n"
                         "You can select a preset template, or choose your own nickname format. You can even set a prefix (text before the nickname) and/or a suffix (text after the nickname)."
            ),
            components=[
                PromptPageData.Component(
                    type="select_menu",
                    placeholder="Select a nickname preset...",
                    min_values=0,
                    max_values=1,
                    component_id="preset_nickname_select",
                    options=[
                        PromptPageData.Component.Option(
                            name="Name users as: Roblox Display Name (@Roblox Username)",
                            value="{smart-name}",
                        ),
                        PromptPageData.Component.Option(
                            name="Name users as: Roblox Username",
                            value="{roblox-name}",
                        ),
                        PromptPageData.Component.Option(
                            name="Name users as: Roblox Display Name",
                            value="{display-name}",
                        ),
                        PromptPageData.Component.Option(
                            name="Name users as: Discord Username",
                            value="{discord-name}",
                        ),
                        PromptPageData.Component.Option(
                            name="Choose my own nickname format...",
                            value="custom",
                        ),
                    ],
                ),
                PromptPageData.Component(
                    type="button",
                    label="Add a nickname prefix (optional)",
                    component_id="nickname_prefix",
                    is_disabled=False,
                ),
                PromptPageData.Component(
                    type="button",
                    label="Add a nickname suffix (optional)",
                    component_id="nickname_suffix",
                    is_disabled=False,
                )
            ],
        )
    )
    async def nickname_page(self, interaction: hikari.ComponentInteraction, fired_component_id: str):
        match fired_component_id:
            case "preset_nickname_select":
                yield await self.next()
            case "nickname_prefix":
                action_row = bloxlink.rest.build_message_action_row()
                action_row.add_component(
                    hikari.TextInputComponent(
                        type=hikari.ComponentType.TEXT_INPUT,
                        custom_id="nickname_prefix_input",
                        value="test"
                    )
                )

                yield self.response.send_modal(
                    title="Add a nickname prefix",
                    custom_id="nickname_prefix_modal",
                    components=[
                        hikari.TextInputComponent(
                            type=hikari.ComponentType.TEXT_INPUT,
                            custom_id="nickname_prefix_input",
                            value="test",
                        )
                    ]
                )
            case "nickname_suffix":
                yield await self.next()

@bloxlink.command(
    category="Administration",
    defer=True,
    defer_with_ephemeral=False,
    permissions=hikari.Permissions.MANAGE_GUILD,
    dm_enabled=False,
    prompts=[SetupPrompt],
)
class SetupCommand:
    """setup Bloxlink for your server"""

    async def __main__(self, ctx: CommandContext):
        print("executing command")
        return await ctx.response.prompt(SetupPrompt)
