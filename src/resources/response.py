import hikari
from typing import Literal

from .exceptions import AlreadyResponded
from dataclasses import dataclass, field
from resources.bloxlink import instance as bloxlink


@dataclass(slots=True)
class EmbedPrompt:
    """Represents a prompt consisting of an embed & components for the message."""

    embed: hikari.Embed = hikari.Embed()
    components: list = field(default_factory=list)

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
        """Defer this interaction. This needs to be yielded and called as the first response.

        Args:
            ephemeral (bool, optional): Should this message be ephemeral. Defaults to False.
        """

        if self.responded:
            raise AlreadyResponded("Cannot defer a response that has already been responded to.")

        self.responded = True

        # if ephemeral:
        #     return await self.interaction.create_initial_response(
        #         hikari.ResponseType.DEFERRED_MESSAGE_UPDATE, flags=hikari.messages.MessageFlag.EPHEMERAL
        #     )

        # return await self.interaction.create_initial_response(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)
        if self.interaction.type == hikari.InteractionType.APPLICATION_COMMAND:
            return self.interaction.build_deferred_response().set_flags(
                hikari.messages.MessageFlag.EPHEMERAL if ephemeral else None
            )

        return self.interaction.build_deferred_response(
            hikari.ResponseType.DEFERRED_MESSAGE_CREATE
        ).set_flags(
            hikari.messages.MessageFlag.EPHEMERAL if ephemeral else None
        )

    def send_first(
        self,
        content: str = None,
        embed: hikari.Embed = None,
        components: list = None,
        ephemeral: bool = False,
        edit_original: bool = False
    ):
        """Directly respond to Discord with this response. This should not be called more than once. This needs to be yielded."""

        """"
        Args:
            content (str, optional): Message content to send. Defaults to None.
            embed (hikari.Embed, optional): Embed to send. Defaults to None.
            components (list, optional): Components to attach to the message. Defaults to None.
            ephemeral (bool, optional): Should this message be ephemeral. Defaults to False.
        """

        if self.responded:
            raise AlreadyResponded("Cannot send a response that has already been responded to.")

        self.responded = True

        if self.interaction.type == hikari.InteractionType.APPLICATION_COMMAND:
            response_builder = self.interaction.build_response().set_flags(hikari.messages.MessageFlag.EPHEMERAL if ephemeral else None)
        else:
            response_builder = self.interaction.build_response(hikari.ResponseType.MESSAGE_CREATE if not edit_original else hikari.ResponseType.MESSAGE_UPDATE).set_flags(hikari.messages.MessageFlag.EPHEMERAL if ephemeral else None)

        if content:
            response_builder.set_content(content)

        if embed:
            response_builder.add_embed(embed)

        if components:
            response_builder.add_component(components[0])


        return response_builder


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
        """Send this Response to discord. This function only sends via REST and ignores the initial webhook response.

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

        if channel:
            return await channel.send(content, embed=embed, components=components, **kwargs)

        if channel_id:
            return await (await bloxlink.rest.fetch_channel(channel_id)).send(
                content, embed=embed, components=components, **kwargs
            )

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

        return await self.interaction.create_initial_response(
            hikari.ResponseType.MESSAGE_CREATE, content, embed=embed, component=components, **kwargs
        )

    async def prompt(self, prompt):
        """Prompt the user with the first page of the prompt."""

        first_page = prompt.pages[0]

        embed_prompt = prompt.embed_prompt(self.interaction.command_name, prompt, first_page)

        await self.send(embed=embed_prompt.embed, components=embed_prompt.components)

class Prompt:
    def __init__(self, command_name: str, response: Response):
        self.pages = []
        self.current_page_number = 1
        self.response = response
        self.command_name = command_name

        for attr_name in dir(self):
            attr = getattr(self, attr_name)

            if hasattr(attr, "__page_details__"):
                self.pages.append({
                    "func": attr,
                    "details": attr.__page_details__,
                    "page_number": len(self.pages) + 1
                })

    @staticmethod
    def page(page_details: dict):
        def wrapper(func):
            func.__page_details__ = page_details
            return func


        return wrapper

    @staticmethod
    def embed_prompt(command_name, prompt, page):
        action_row = bloxlink.rest.build_message_action_row()

        for component in page["details"].components:
            if component.type == "button":
                action_row.add_interactive_button(
                    hikari.ButtonStyle.PRIMARY,
                    f"{command_name}:prompt:{prompt.__class__.__name__}:{page['page_number']}",
                    label=component.label,
                )

        return EmbedPrompt(
            embed=hikari.Embed(
                title="Prompt",
                description=page["details"].description,
            ),
            components=[action_row]
        )

    async def handle(self, interaction):
        """Entry point when a component is called. Redirect to the correct page."""

        custom_id = interaction.custom_id

        prompt_data = custom_id.split(":")
        current_page_number = int(prompt_data[3])

        self.current_page_number = current_page_number

        yield (await (self.pages[current_page_number-1]["func"]()).__anext__())

    def next(self):
        """Go to the next page of the prompt."""

        self.current_page_number += 1

        embed_prompt = self.embed_prompt(self.command_name, self, self.pages[self.current_page_number-1])

        return self.response.send_first(embed=embed_prompt.embed, components=embed_prompt.components, edit_original=True)

    def finish(self, content: str = "Finished prompt.", embed: hikari.Embed = None, components: list = None):
        """Finish the prompt."""

        return self.response.send_first(content=content, embed=embed, components=components, edit_original=True)

@dataclass(slots=True)
class PromptPageData:
    description: str
    components: list = field(default_factory=list)

    @dataclass(slots=True)
    class Component:
        type: Literal["button"]
        label: str
