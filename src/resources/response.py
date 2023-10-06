import hikari


class Response:
    """Response to a discord interaction.

    Attributes:
        interaction (hikari.CommandInteraction): Interaction that this response is for.
        responded (bool): Has this interaction been responded to. Default is False.
        deferred (bool): Is this response a deferred response. Default is False.
    """

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
        """Send this Response to discord.

        Args:
            content (str, optional): Message content to send. Defaults to None.
            embed (hikari.Embed, optional): Embed to send. Defaults to None.
            components (list, optional): Components to attach to the message. Defaults to None.
            **kwargs: match what hikari expects for interaction.execute() or interaction.create_initial_response()
        """
        if self.responded:
            if isinstance(components, (list, tuple)):
                await self.interaction.execute(content, embed=embed, components=components, **kwargs)
            else:
                await self.interaction.execute(content, embed=embed, component=components, **kwargs)

        else:
            self.responded = True

            if isinstance(components, (list, tuple)):
                await self.interaction.create_initial_response(
                    hikari.ResponseType.MESSAGE_CREATE, content, embed=embed, components=components, **kwargs
                )
            else:
                await self.interaction.create_initial_response(
                    hikari.ResponseType.MESSAGE_CREATE, content, embed=embed, component=components, **kwargs
                )
