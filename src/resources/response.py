from collections.abc import Iterable

import hikari

from .bloxlink import instance as bloxlink


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

    def defer(self, ephemeral: bool = False):
        """Defer this interaction.

        Args:
            ephemeral (bool, optional): Should this message be ephemeral. Defaults to False.
        """

        if self.responded:
            raise ValueError("Cannot defer a response that has already been responded to.")

        self.responded = True

        # if ephemeral:
        #     return await self.interaction.create_initial_response(
        #         hikari.ResponseType.DEFERRED_MESSAGE_UPDATE, flags=hikari.messages.MessageFlag.EPHEMERAL
        #     )

        # return await self.interaction.create_initial_response(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)
        return self.interaction.build_deferred_response(
            hikari.ResponseType.DEFERRED_MESSAGE_CREATE
        ).set_flags(
            hikari.messages.MessageFlag.EPHEMERAL if ephemeral else None
        )

    async def send(
        self,
        content: str = None,
        embed: hikari.Embed = None,
        components: list = None,
        ephemeral: bool = False,
        channel: hikari.GuildTextChannel = None,
        channel_id: str | int = None,
        **kwargs,
    ):
        """Send this Response to discord.

        Args:
            content (str, optional): Message content to send. Defaults to None.
            embed (hikari.Embed, optional): Embed to send. Defaults to None.
            components (list, optional): Components to attach to the message. Defaults to None.
            ephemeral (bool, optional): Should this message be ephemeral. Defaults to False.
            channel (hikari.GuildTextChannel, optional): Channel to send the message to. This will send as a regular message, not as an interaction response. Defaults to None.
            channel_id (int, str, optional): Channel ID to send the message to. This will send as a regular message, not as an interaction response. Defaults to None.
            **kwargs: match what hikari expects for interaction.execute() or interaction.create_initial_response()
        """

        if channel and channel_id:
            raise ValueError("Cannot specify both channel and channel_id.")

        if not isinstance(components, Iterable):
            components = [components]

        if channel:
            return await channel.send(content, embed=embed, components=components, **kwargs)

        if channel_id:
            # FIXME: bloxlink is None
            # return await (await bloxlink.rest.fetch_channel(channel_id)).send(
            #     content, embed=embed, components=components, **kwargs
            # )
            pass

        if ephemeral:
            kwargs["flags"] = hikari.messages.MessageFlag.EPHEMERAL

        if self.deferred:
            self.deferred = False
            self.responded = True

            kwargs.pop("flags", None)  # edit_initial_response doesn't support ephemeral

            return await self.interaction.edit_initial_response(
                content, embed=embed, components=components, **kwargs
            )

        if self.responded:
            return await self.interaction.execute(content, embed=embed, components=components, **kwargs)

        self.responded = True

        # return await self.interaction.create_initial_response(
        #     hikari.ResponseType.MESSAGE_CREATE, content, embed=embed, component=components, **kwargs
        # )

        response_builder = self.interaction.build_response(hikari.ResponseType.MESSAGE_CREATE).set_content(content).set_flags(hikari.messages.MessageFlag.EPHEMERAL if ephemeral else None)

        if embed:
            response_builder.add_embed(embed)

        if components:
            response_builder.add_component(components)


        return response_builder
