from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext
from resources.response import Prompt, Response, PromptPageData


class PingPrompts(Prompt):
    def __init__(self, interaction, response: Response):
        super().__init__(interaction, response, self.__class__.__name__)

    @Prompt.page(
        PromptPageData(
            title="Ping Prompt",
            description="Select a role then click Next.",
            components=[
                PromptPageData.Component(
                    type="role_select_menu",
                    placeholder="Select a role",
                    min_values=0,
                    max_values=1,
                    custom_id="role_select",
                ),
                PromptPageData.Component(
                    type="button",
                    label="Back",
                    custom_id="back",
                    is_disabled=True
                ),
                PromptPageData.Component(
                    type="button",
                    label="Next",
                    custom_id="next",
                    is_disabled=True
                )
            ]
        )
    )
    async def page1(self, interaction):
        # yield await self.response.defer()

        if interaction.custom_id == "next":
            # yield await self.next()
            yield await self.go_to(self.page2)
            return

        current_data = await self.current_data()

        role_selected = current_data['role_select']['values'][0] if current_data['role_select']['values'] else None

        if role_selected:
            yield await self.edit_component(
                "next",
                is_disabled=False
            )

    @Prompt.page(
        PromptPageData(
            description="hi 2",
            components=[
                PromptPageData.Component(
                    type="button",
                    label="Back",
                    custom_id="back",
                    is_disabled=False
                ),
                PromptPageData.Component(
                    type="button",
                    label="Next",
                    custom_id="finish"
                )
            ]
        )
    )
    async def page2(self, interaction):
        print("page2")

        if interaction.custom_id == "back":
            yield await self.previous()
            return

        # yield await self.next()
        yield await self.go_to(self.page3)

    @Prompt.page(
        PromptPageData(
            description="hi 3",
            components=[
                PromptPageData.Component(
                    type="button",
                    label="Finish",
                    custom_id="finish"
                )
            ]
        )
    )
    async def page3(self, interaction):
        print("page3")

        yield await self.finish("Finished")


@bloxlink.command(
    category="Miscellaneous",
    prompts=[PingPrompts]
)
class PingCommand:
    """check if the bot is alive"""

    async def __main__(self, ctx: CommandContext):
        await ctx.response.prompt(PingPrompts)
