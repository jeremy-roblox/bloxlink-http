import hikari
from typing import Literal, Callable, Type
from attrs import define, field
import json

from .exceptions import AlreadyResponded, CancelCommand, PageNotFound
from resources.bloxlink import instance as bloxlink
import resources.component_helper as component_helper


@define(slots=True)
class EmbedPrompt:
    """Represents a prompt consisting of an embed & components for the message."""

    embed: hikari.Embed = hikari.Embed()
    components: list = field(factory=list)

@define
class PromptCustomID:
    """Represents a custom ID for a prompt component."""

    command_name: str
    prompt_name: str
    user_id: int = field(converter=int)
    page_number: int = field(converter=int)
    component_custom_id: str

@define(slots=True)
class PromptPageData:
    description: str
    components: list['Component'] = field(default=list())
    title: str = None

    @define(slots=True)
    class Component:
        type: Literal["button", "role_select_menu", "select_menu"]
        custom_id: str
        label: str = None
        placeholder: str = None
        min_values: int = None
        max_values: int = None
        is_disabled: bool = False
        options: list['Option'] = None
        on_submit: Callable = None

        @define(slots=True)
        class Option:
            name: str
            value: str
            description: str = None
            is_default: bool = False


@define(slots=True)
class Page:
    func: Callable
    details: PromptPageData
    page_number: int
    programmatic: bool = False


class Response:
    """Response to a discord interaction.

    Attributes:
        interaction (hikari.CommandInteraction): Interaction that this response is for.
        user_id (hikari.Snowflake): The user ID who triggered this interaction.
        responded (bool): Has this interaction been responded to. Default is False.
        deferred (bool): Is this response a deferred response. Default is False.
    """

    def __init__(self, interaction: hikari.CommandInteraction):
        self.interaction = interaction
        self.user_id = interaction.user.id
        self.responded = False
        self.deferred = False
        self.defer_through_rest = False

    async def defer(self, ephemeral: bool = False):
        """Defer this interaction. This needs to be yielded and called as the first response.

        Args:
            ephemeral (bool, optional): Should this message be ephemeral. Defaults to False.
        """

        if self.responded:
            raise AlreadyResponded("Cannot defer a response that has already been responded to.")

        self.responded = True
        self.deferred = True

        if self.defer_through_rest:
            if ephemeral:
                return await self.interaction.create_initial_response(
                    hikari.ResponseType.DEFERRED_MESSAGE_UPDATE, flags=hikari.messages.MessageFlag.EPHEMERAL
                )

            return await self.interaction.create_initial_response(hikari.ResponseType.DEFERRED_MESSAGE_UPDATE)

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
        # else:
        #     response_builder.clear_content()

        if embed:
            response_builder.add_embed(embed)
        # else:
        #     response_builder.clear_embeds()

        if components:
            for component in components:
                response_builder.add_component(component)
        else:
            response_builder.clear_components()

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
            hikari.ResponseType.MESSAGE_CREATE, content, embed=embed, components=components, **kwargs
        )

    async def prompt(self, prompt: Type['Prompt']):
        """Prompt the user with the first page of the prompt."""

        if self.interaction.type != hikari.InteractionType.APPLICATION_COMMAND:
            raise NotImplementedError("Can only call prompt() from a slash command.")

        new_prompt = prompt(self.interaction.command_name, self)
        new_prompt.insert_pages(prompt)

        first_page = new_prompt.pages[0]

        if first_page.programmatic:
            page_details: PromptPageData = await first_page.func(self.interaction)

            first_page.details = page_details

        embed_prompt = new_prompt.embed_prompt(self.interaction.command_name, self.user_id, first_page)

        await self.send(embed=embed_prompt.embed, components=embed_prompt.components)

class Prompt:
    def __init__(self, command_name: str, response: Response, prompt_name: str):
        self.pages: list[Page] = []
        self.current_page_number = 0
        self.response = response
        self.command_name = command_name
        self.prompt_name = prompt_name

        response.defer_through_rest = True

    @staticmethod
    def page(page_details: PromptPageData):
        def wrapper(func: Callable):
            func.__page_details__ = page_details
            func.__programmatic_page__ = False
            func.__page__ = True
            return func

        return wrapper

    @staticmethod
    def programmatic_page():
        def wrapper(func: Callable):
            func.__page_details__ = None
            func.__programmatic_page__ = True
            func.__page__ = True
            return func

        return wrapper

    def embed_prompt(self, command_name: str, user_id: int, page: Page):
        """Build an EmbedPrompt from a prompt and page."""

        components = []

        if page.details.components:
            button_action_row = bloxlink.rest.build_message_action_row()
            has_button = False

            for component in page.details.components:
                parsed_custom_id = component_helper.get_custom_id(
                    PromptCustomID,
                    command_name=command_name,
                    prompt_name=self.__class__.__name__,
                    page_number=page.page_number,
                    component_custom_id=component.custom_id,
                    user_id=user_id
                )
                if component.type == "button":
                    button_action_row.add_interactive_button(
                        hikari.ButtonStyle.PRIMARY,
                        parsed_custom_id,
                        label=component.label,
                        is_disabled=component.is_disabled
                    )
                    has_button = True
                elif component.type == "role_select_menu":
                    role_action_row = bloxlink.rest.build_message_action_row()
                    role_action_row.add_select_menu(
                        hikari.ComponentType.ROLE_SELECT_MENU,
                        parsed_custom_id,
                        placeholder=component.placeholder,
                        min_values=component.min_values,
                        max_values=component.max_values,
                        is_disabled=component.is_disabled
                    )
                    components.append(role_action_row)
                elif component.type == "select_menu":
                    text_action_row = bloxlink.rest.build_message_action_row()
                    text_menu = text_action_row.add_text_menu(
                        parsed_custom_id,
                        placeholder=component.placeholder,
                        min_values=component.min_values,
                        max_values=component.max_values,
                        is_disabled=component.is_disabled
                    )
                    for option in component.options:
                        text_menu.add_option(
                            option.name,
                            option.value,
                            description=option.description,
                            is_default=option.is_default
                        )

                    components.append(text_action_row)

            if has_button:
                components.append(button_action_row)

        return EmbedPrompt(
            embed=hikari.Embed(
                title=page.details.title or "Prompt",
                description=page.details.description,
            ),
            components=components if components else None
        )

    def insert_pages(self, prompt: Type['Prompt']):
        """Get all pages from the prompt.

        This needs to be called OUTSIDE of self to get the class attributes in insertion-order.

        """

        page_number = 0

        for attr_name, attr in prompt.__dict__.items(): # so we can get the class attributes in insertion-order
            if hasattr(attr, "__page__"):
                if getattr(attr, "__programmatic_page__", False):
                    self.pages.append(Page(func=getattr(self, attr_name), programmatic=True, details=PromptPageData(description="Programmatic page", components=[]), page_number=page_number))
                else:
                    self.pages.append(Page(func=getattr(self, attr_name), details=attr.__page_details__, page_number=page_number))

                page_number += 1

    async def populate_programmatic_page(self, interaction: hikari.ComponentInteraction):
        current_page = self.pages[self.current_page_number]

        if current_page.programmatic:
            generator_or_coroutine = current_page.func(interaction)

            if hasattr(generator_or_coroutine, "__anext__"):
                await generator_or_coroutine.__anext__() # usually a response builder object
                page_details: PromptPageData = await generator_or_coroutine.__anext__() # actual page details
            else:
                page_details: PromptPageData = await generator_or_coroutine

            current_page.details = page_details

    async def handle(self, interaction: hikari.ComponentInteraction):
        """Entry point when a component is called. Redirect to the correct page."""

        custom_id = component_helper.parse_custom_id(PromptCustomID, interaction.custom_id)

        current_page_number = custom_id.page_number
        component_custom_id = custom_id.component_custom_id

        if interaction.user.id != custom_id.user_id:
            yield await self.response.send_first(f"This prompt can only be used by <@{custom_id.user_id}>.", ephemeral=True)
            return

        self.current_page_number = current_page_number
        interaction.custom_id = component_custom_id # TODO: make a better solution

        current_page = self.pages[current_page_number]

        if current_page.programmatic:
            # we need to fire the programmatic page to know what to do when the component is activated
            await self.populate_programmatic_page(interaction)

            for component in current_page.details.components:
                if component.custom_id == component_custom_id:
                    # TODO assume it's a page
                    yield await self.go_to(component.on_submit)
                    return

        generator_or_coroutine = current_page.func(interaction)

        if hasattr(generator_or_coroutine, "__anext__"):
            async for generator_response in generator_or_coroutine:
                yield generator_response
        else:
            await generator_or_coroutine

    async def current_data(self, raise_exception: bool = True):
        """Get the data for the current page from Redis."""

        redis_data = await bloxlink.redis.get(f"prompt_data:{self.command_name}:{self.prompt_name}:{self.response.interaction.user.id}")

        if not redis_data:
            if raise_exception:
                raise CancelCommand("Previous data not found. Please restart this command.")

            return {}

        return json.loads(redis_data)


    async def save_data(self, interaction: hikari.ComponentInteraction):
        """Save the data from the interaction from the current page to Redis."""

        custom_id = component_helper.parse_custom_id(PromptCustomID, interaction.custom_id)
        component_custom_id = custom_id.component_custom_id

        data = await self.current_data(raise_exception=False)
        data[component_custom_id] = component_helper.component_values_to_dict(interaction)

        await bloxlink.redis.set(f"prompt_data:{self.command_name}:{self.prompt_name}:{interaction.user.id}", json.dumps(data), ex=5*60)

    async def previous(self, content: str=None):
        """Go to the previous page of the prompt."""

        self.current_page_number -= 1

        await self.populate_programmatic_page(self.response.interaction)

        embed_prompt = self.embed_prompt(self.command_name, self.response.user_id, self.pages[self.current_page_number])

        return await self.response.send_first(content=content, embed=embed_prompt.embed, components=embed_prompt.components, edit_original=True)

    async def next(self, content: str=None):
        """Go to the next page of the prompt."""

        self.current_page_number += 1

        await self.populate_programmatic_page(self.response.interaction)

        embed_prompt = self.embed_prompt(self.command_name, self.response.user_id, self.pages[self.current_page_number])

        return await self.response.send_first(content=content, embed=embed_prompt.embed, components=embed_prompt.components, edit_original=True)

    async def go_to(self, page: Callable, content: str=None):
        """Go to a specific page of the prompt."""

        for this_page in self.pages:
            if this_page.func == page:
                self.current_page_number = this_page.page_number
                break
        else:
            raise PageNotFound(f"Page {page} not found.")

        await self.populate_programmatic_page(self.response.interaction)

        embed_prompt = self.embed_prompt(self.command_name, self.response.user_id, self.pages[self.current_page_number])

        return await self.response.send_first(content=content, embed=embed_prompt.embed, components=embed_prompt.components, edit_original=True)

    async def finish(self, content: str = "Finished prompt.", embed: hikari.Embed = None, components: list[hikari.ActionRowComponent] = None):
        """Finish the prompt."""

        return await self.response.send_first(content=content, embed=embed, components=components, edit_original=True)

    async def edit_component(self, custom_id: str, **kwargs):
        """Edit a component on the current page."""

        current_page = self.pages[self.current_page_number]

        for component in current_page.details.components:
            if component.custom_id == custom_id:
                for attr_name, attr_value in kwargs.items():
                    setattr(component, attr_name, attr_value)

        embed_prompt = self.embed_prompt(self.command_name, self.response.user_id, self.pages[self.current_page_number])

        return await self.response.send_first(embed=embed_prompt.embed, components=embed_prompt.components, edit_original=True)
