import hikari
from typing import Literal
import json

from .exceptions import AlreadyResponded, CancelCommand
from dataclasses import dataclass, field
from resources.bloxlink import instance as bloxlink
import resources.component_helper as component_helper


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
        self.deferred = True

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

    async def send_first(
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
            if edit_original:
                return await self.interaction.edit_initial_response(content, embed=embed, components=components)

            return await self.send(content, embed=embed, components=components, ephemeral=ephemeral)

        self.responded = True

        if self.interaction.type == hikari.InteractionType.APPLICATION_COMMAND:
            response_builder = self.interaction.build_response().set_flags(hikari.messages.MessageFlag.EPHEMERAL if ephemeral else None)
        elif self.interaction.type == hikari.InteractionType.MESSAGE_COMPONENT:
            response_builder = self.interaction.build_response(hikari.ResponseType.MESSAGE_CREATE if not edit_original else hikari.ResponseType.MESSAGE_UPDATE).set_flags(hikari.messages.MessageFlag.EPHEMERAL if ephemeral else None)
        else:
            raise NotImplementedError()

        if content:
            response_builder.set_content(content)

        if embed:
            response_builder.add_embed(embed)

        if components:
            for component in components:
                response_builder.add_component(component)

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
    def __init__(self, command_name: str, response: Response, prompt_name: str):
        self.pages = []
        self.current_page_number = 0
        self.response = response
        self.command_name = command_name
        self.prompt_name = prompt_name

        for attr_name in dir(self):
            attr = getattr(self, attr_name)

            if hasattr(attr, "__page_details__"):
                self.pages.append({
                    "func": attr,
                    "details": attr.__page_details__,
                    "page_number": len(self.pages)
                })

    @staticmethod
    def page(page_details: dict):
        def wrapper(func):
            func.__page_details__ = page_details
            return func


        return wrapper

    @staticmethod
    def embed_prompt(command_name, prompt, page):
        """Build an EmbedPrompt from a prompt and page."""

        button_action_row = bloxlink.rest.build_message_action_row()
        components = []

        for component in page["details"].components:
            if component.type == "button":
                button_action_row.add_interactive_button(
                    hikari.ButtonStyle.PRIMARY,
                    f"{command_name}:{prompt.__class__.__name__}:{page['page_number']}:{component.custom_id}",
                    label=component.label,
                    is_disabled=component.is_disabled
                )
            elif component.type == "role_select_menu":
                role_action_row = bloxlink.rest.build_message_action_row()
                role_action_row.add_select_menu(
                    hikari.ComponentType.ROLE_SELECT_MENU,
                    f"{command_name}:{prompt.__class__.__name__}:{page['page_number']}:{component.custom_id}",
                    placeholder=component.placeholder,
                    min_values=component.min_values,
                    max_values=component.max_values,
                    is_disabled=component.is_disabled
                )
                components.append(role_action_row)

        components.append(button_action_row)

        return EmbedPrompt(
            embed=hikari.Embed(
                title=page["details"].title or "Prompt",
                description=page["details"].description,
            ),
            components=components
        )

    async def handle(self, interaction):
        """Entry point when a component is called. Redirect to the correct page."""

        custom_id = interaction.custom_id

        prompt_data = custom_id.split(":")
        current_page_number = int(prompt_data[2])
        component_custom_id = prompt_data[3]

        self.current_page_number = current_page_number
        interaction.custom_id = component_custom_id # TODO: make a better solution

        generator_or_coroutine = self.pages[current_page_number]["func"](interaction)

        if hasattr(generator_or_coroutine, "__anext__"):
            async for generator_response in self.pages[current_page_number]["func"](interaction):
                yield generator_response
        else:
            await generator_or_coroutine

    async def current_data(self, raise_exception: bool = True):
        """Get the data for the current page from Redis."""

        redis_data = await bloxlink.redis.get(f"prompt_data:{self.command_name}:{self.prompt_name}:{self.response.interaction.user.id}")

        if not redis_data:
            if raise_exception:
                raise CancelCommand("Previous data not found. Please restart this command.")
            else:
                return {}

        return json.loads(redis_data)


    async def save_data(self, interaction: hikari.ComponentInteraction):
        """Save the data from the current page to Redis."""

        component_custom_id = interaction.custom_id.split(":")[3]

        data = await self.current_data(raise_exception=False)
        data[component_custom_id] = component_helper.component_values_to_dict(interaction)

        await bloxlink.redis.set(f"prompt_data:{self.command_name}:{self.prompt_name}:{interaction.user.id}", json.dumps(data), ex=5*60)

    async def next(self, content=None):
        """Go to the next page of the prompt."""

        self.current_page_number += 1

        embed_prompt = self.embed_prompt(self.command_name, self, self.pages[self.current_page_number])

        return await self.response.send_first(content=content, embed=embed_prompt.embed, components=embed_prompt.components, edit_original=True)

    async def finish(self, content: str = "Finished prompt.", embed: hikari.Embed = None, components: list = None):
        """Finish the prompt."""

        return await self.response.send_first(content=content, embed=embed, components=components, edit_original=True)

    async def edit_component(self, custom_id, **kwargs):
        """Edit a component on the current page."""

        current_page = self.pages[self.current_page_number]

        for component in current_page["details"].components:
            if component.custom_id.endswith(custom_id):
                for attr_name, attr_value in kwargs.items():
                    setattr(component, attr_name, attr_value)

        embed_prompt = self.embed_prompt(self.command_name, self, self.pages[self.current_page_number])

        return await self.response.send_first(embed=embed_prompt.embed, components=embed_prompt.components, edit_original=True)

@dataclass(slots=True)
class PromptPageData:
    description: str
    components: list = field(default_factory=list)
    title: str = None

    @dataclass(slots=True)
    class Component:
        type: Literal["button", "role_select_menu"]
        custom_id: str
        label: str = None
        placeholder: str = None
        min_values: int = None
        max_values: int = None
        is_disabled: bool = False
