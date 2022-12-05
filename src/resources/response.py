import hikari



class Response:
    def __init__(self, interaction:hikari.CommandInteraction):
        self.interaction = interaction
        self._responded = False


    async def send(self, content, **kwargs):
        if self._responded:
            await self.interaction.execute(content, **kwargs)
        else:
            self._responded = True
            await self.interaction.create_initial_response(
                hikari.ResponseType.MESSAGE_CREATE,
                content, **kwargs)

    async def defer(self):
        if self._responded:
            raise RuntimeError("Cannot defer if the interaction has been responded to!")

        self._responded = True
        await self.interaction.create_initial_response(
            hikari.ResponseType.DEFERRED_MESSAGE_CREATE)
