import hikari



class Response:
    def __init__(self, interaction: hikari.CommandInteraction):
        self.interaction = interaction
        self._responded = False
        self._responded_once = False # if True, we respond to Discord with the content
        self.responded_once_content: dict | None = None # we respond to Discord with this


    async def send(self, content: str | None = None, embed: hikari.Embed | None = None, **kwargs):
        if self._responded:
            self.responded_once = False
            self.responded_once_content = None
            await self.interaction.execute(content, embed=embed, **kwargs)
        else:
            self._responded = True
            self.responded_once = True
            self.responded_once_content = {
                "content": content,
                "embed": embed,
                **kwargs
            }

            await self.interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE,
                content, embed=embed, **kwargs)

    async def defer(self):
        if self._responded:
            raise RuntimeError("Cannot defer if the interaction has been responded to!")

        self._responded = True
        await self.interaction.create_initial_response(
            hikari.ResponseType.DEFERRED_MESSAGE_CREATE)
