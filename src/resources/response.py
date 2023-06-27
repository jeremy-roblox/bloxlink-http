import hikari


class Response:
    def __init__(self, interaction: hikari.CommandInteraction):
        self.interaction = interaction
        self.responded = False
        self.deferred = False

    async def send(
        self,
        content: str = None,
        embed: hikari.Embed = None,
        components: list = None,
        **kwargs,
    ):
        if self.responded:
            if isinstance(components, list):
                await self.interaction.execute(content, embed=embed, components=components, **kwargs)
            else:
                await self.interaction.execute(content, embed=embed, component=components, **kwargs)

        else:
            self.responded = True

            if isinstance(components, list):
                await self.interaction.create_initial_response(
                    hikari.ResponseType.MESSAGE_CREATE, content, embed=embed, components=components, **kwargs
                )
            else:
                await self.interaction.create_initial_response(
                    hikari.ResponseType.MESSAGE_CREATE, content, embed=embed, component=components, **kwargs
                )
