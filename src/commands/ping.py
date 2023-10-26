from resources.bloxlink import instance as bloxlink
from resources.commands import CommandContext
from resources.response import Prompt, Response, PromptPageData


class PingPrompts(Prompt):
    def __init__(self, interaction, response: Response):
        super().__init__(interaction, response)

    @Prompt.page(
        PromptPageData(
            description="hi 1",
            components=[
                PromptPageData.Component(
                    type="button",
                    label="Next",
                )
            ]
        )
    )
    async def page1(self):
        print("page1")

        yield self.next()

    @Prompt.page(
        PromptPageData(
            description="hi 2",
            components=[
                PromptPageData.Component(
                    type="button",
                    label="Finish",
                )
            ]
        )
    )
    async def page2(self):
        print("page2")

        yield self.finish("Finished")


@bloxlink.command(
    category="Miscellaneous",
    prompts=[PingPrompts]
)
class PingCommand:
    """check if the bot is alive"""

    async def __main__(self, ctx: CommandContext):
        yield ctx.response.send_first("pong")

        await ctx.response.prompt(PingPrompts(ctx.command_name, ctx.response))
