import hikari
from typing import Literal, Callable, Type
from attrs import define, field, fields
import json

from .exceptions import AlreadyResponded, CancelCommand, PageNotFound
from resources.bloxlink import instance as bloxlink
import resources.component_helper as component_helper
import uuid


@define(slots=True)
class EmbedPrompt:
    """Represents a prompt consisting of an embed & components for the message."""

    embed: hikari.Embed = hikari.Embed()
    components: list = field(factory=list)
    page_number: int = 0

@define
class PromptCustomID:
    """Represents a custom ID for a prompt component."""

    command_name: str
    prompt_name: str
    user_id: int = field(converter=int)
    page_number: int = field(converter=int)
    component_custom_id: str

    def __str__(self):
        field_values = [str(getattr(self, field.name)) for field in fields(self.__class__)]
        return ":".join(field_values)

@define(slots=True)
class PromptPageData:
    description: str
    components: list['Component'] = field(default=list())
    title: str = None

    @define(slots=True)
    class Component:
        type: Literal["button", "role_select_menu", "select_menu"]
        component_id: str
        label: str = None
        placeholder: str = None
        style: Literal[hikari.ButtonStyle.PRIMARY, hikari.ButtonStyle.SECONDARY, hikari.ButtonStyle.SUCCESS, hikari.ButtonStyle.DANGER, hikari.ButtonStyle.LINK] = None
        min_values: int = None
        max_values: int = None
        is_disabled: bool = False
        options: list['Option'] = None
        # on_submit: Callable = None

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
    unparsed_programmatic: bool = False
    edited: bool = False


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
            # raise AlreadyResponded("Cannot defer a response that has already been responded to.")
            return

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

        print("responded=", self.responded)

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

        print(response_builder)

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

    async def prompt(self, prompt: Type['Prompt'], custom_id_data: dict = None):
        """Prompt the user with the first page of the prompt."""

        if self.interaction.type != hikari.InteractionType.APPLICATION_COMMAND:
            raise NotImplementedError("Can only call prompt() from a slash command.")

        new_prompt = prompt(self.interaction.command_name, self)
        new_prompt.insert_pages(prompt)

        first_page = new_prompt.pages[0]

        # if first_page.programmatic:
        #     await new_prompt.populate_programmatic_page(self.interaction)

        # built_page = new_prompt.build_page(self.interaction.command_name, self.user_id, first_page, custom_id_data)

        # return await self.send_first(embed=built_page.embed, components=built_page.components, edit_original=True)

        hash_ = uuid.uuid4().hex
        print("prompt() hash=", hash_)
        return await new_prompt.run_page(custom_id_data, hash_=hash_).__anext__()

class Prompt:
    def __init__(self, command_name: str, response: Response, prompt_name: str, custom_id_format: Type[Callable]=PromptCustomID):
        self.pages: list[Page] = []
        self.current_page_number = 0
        self.response = response
        self.command_name = command_name
        self.prompt_name = prompt_name
        self.custom_id_format = custom_id_format
        self.custom_id: PromptCustomID = None # only set if the component is activated

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

    def build_page(self, command_name: str, user_id: int, page: Page, custom_id_data: dict = None, hash_=None):
        """Build an EmbedPrompt from a prompt and page."""

        components = []

        if not self.custom_id:
            # this is only fired when response.prompt() is called
            print(page.page_number)
            self.custom_id = self.custom_id_format(
                command_name=command_name,
                prompt_name=self.__class__.__name__,
                page_number=page.page_number,
                component_custom_id="none",
                user_id=user_id,
                **(custom_id_data or {})
            )

        self.custom_id.page_number = page.page_number

        if page.details.components:
            button_action_row = bloxlink.rest.build_message_action_row()
            has_button = False

            for component in page.details.components:
                component_custom_id = component_helper.set_custom_id_field(self.custom_id_format, str(self.custom_id), component_custom_id=component.component_id)
                print(hash_, "oof", component_custom_id, page)

                if component.type == "button":
                    button_action_row.add_interactive_button(
                        component.style or hikari.ButtonStyle.PRIMARY,
                        component_custom_id,
                        label=component.label,
                        is_disabled=component.is_disabled
                    )
                    has_button = True
                elif component.type == "role_select_menu":
                    role_action_row = bloxlink.rest.build_message_action_row()
                    role_action_row.add_select_menu(
                        hikari.ComponentType.ROLE_SELECT_MENU,
                        component_custom_id,
                        placeholder=component.placeholder,
                        min_values=component.min_values,
                        max_values=component.max_values,
                        is_disabled=component.is_disabled
                    )
                    components.append(role_action_row)
                elif component.type == "select_menu":
                    text_action_row = bloxlink.rest.build_message_action_row()
                    text_menu = text_action_row.add_text_menu(
                        component_custom_id,
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

        print(components)

        return EmbedPrompt(
            embed=hikari.Embed(
                title=page.details.title or "Prompt",
                description=page.details.description,
            ),
            components=components if components else None,
            page_number=page.page_number
        )

    def insert_pages(self, prompt: Type['Prompt']):
        """Get all pages from the prompt.

        This needs to be called OUTSIDE of self to get the class attributes in insertion-order.

        """

        page_number = 0

        for attr_name, attr in prompt.__dict__.items(): # so we can get the class attributes in insertion-order
            if hasattr(attr, "__page__"):
                if getattr(attr, "__programmatic_page__", False):
                    self.pages.append(Page(func=getattr(self, attr_name), programmatic=True, unparsed_programmatic=True, details=PromptPageData(description="Unparsed programmatic page", components=[]), page_number=page_number))
                else:
                    self.pages.append(Page(func=getattr(self, attr_name), details=attr.__page_details__, page_number=page_number))

                page_number += 1

    async def populate_programmatic_page(self, interaction: hikari.ComponentInteraction, fired_component_id: str | None = None):
        current_page = self.pages[self.current_page_number]
        print("current_page=", current_page)

        # if current_page.programmatic and current_page.unparsed_programmatic:
        #     generator_or_coroutine = current_page.func(interaction, fired_component_id)

        #     if hasattr(generator_or_coroutine, "__anext__"):
        #         async for generator_response in generator_or_coroutine:
        #             if isinstance(generator_response, PromptPageData):
        #                 page_details = generator_response
        #                 # break
        #             else:
        #                 yield generator_response
        #             # await generator_response
        #         # await generator_or_coroutine.__anext__() # usually a response builder object
        #         # page_details: PromptPageData = await generator_or_coroutine.__anext__() # actual page details
        #     else:
        #         page_details: PromptPageData = await generator_or_coroutine

        #     current_page.details = page_details
        #     current_page.unparsed_programmatic = False
        #     print("populate_programmatic_page details=", current_page.details)

        if current_page.programmatic and current_page.unparsed_programmatic:
            generator_or_coroutine = current_page.func(interaction, fired_component_id)
            if hasattr(generator_or_coroutine, "__anext__"):
                async for generator_response in generator_or_coroutine:
                    if not generator_response:
                        continue

                    if isinstance(generator_response, PromptPageData):
                        page_details = generator_response
                        # break
                    # else:
                    #     yield generator_response
                        # await generator_response
                # await generator_or_coroutine.__anext__() # usually a response builder object
                # page_details: PromptPageData = await generator_or_coroutine.__anext__() # actual page details
            else:
                page_details: PromptPageData = await generator_or_coroutine

            current_page.details = page_details
            # built_page = self.build_page(self.command_name, self.response.user_id, current_page, custom_id_data, hash_)



    async def entry_point(self, interaction: hikari.ComponentInteraction):
        """Entry point when a component is called. Redirect to the correct page."""

        self.custom_id = component_helper.parse_custom_id(self.custom_id_format, interaction.custom_id)
        self.current_page_number = self.custom_id.page_number
        self.current_page = self.pages[self.current_page_number]
        # print(self.custom_id)

        component_custom_id = self.custom_id.component_custom_id
        # print("component_custom_id", component_custom_id)

        if interaction.user.id != self.custom_id.user_id:
            yield await self.response.send_first(f"This prompt can only be used by <@{self.custom_id.user_id}>.", ephemeral=True)
            return

        # if current_page.programmatic:
        #     return

        # if current_page.programmatic:
        #     # we need to fire the programmatic page to know what to do when the component is activated
        #     await self.populate_programmatic_page(interaction)

        #     for component in current_page.details.components:
        #         if component.custom_id == component_custom_id:
        #             if component.on_submit:
        #                 # TODO assume it's a page
        #                 yield await self.go_to(component.on_submit)
        #                 break

        #     return

        # print(5, self.response.responded)

        # if self.current_page.programmatic:
        #     yield await self.populate_programmatic_page(interaction, component_custom_id)
        #     print(6, self.response.responded)
        #     return
        #     # built_page = self.build_page(self.command_name, self.response.user_id, self.pages[self.current_page_number])

        #     # yield await self.response.send_first(embed=built_page.embed, components=built_page.components, edit_original=True)

        #     # return



        # generator_or_coroutine = self.current_page.func(interaction, component_custom_id)
        # print("generator_or_coroutine", generator_or_coroutine)

        # if hasattr(generator_or_coroutine, "__anext__"):
        #     async for generator_response in generator_or_coroutine:
        #         print("generator_response", generator_response)
        #         yield generator_response
        # else:
        #     await generator_or_coroutine

        hash_ = uuid.uuid4().hex
        print("entry_point() hash=", hash_)

        async for generator_response in self.run_page(hash_=hash_):
            # print("running page entry_point()", generator_response)
            if isinstance(generator_response, hikari.Message):
                continue
            print(hash_, "generator_response entry_point()", generator_response)
            yield generator_response

        # return await self.run_page().__anext__()

    async def run_page(self, custom_id_data: dict = None, hash_=None):
        """Run the current page."""

        hash_ = hash_ or uuid.uuid4().hex

        current_page = self.pages[self.current_page_number]
        print(hash_, "current page number", self.current_page_number)

        # if current_page.programmatic:
        #     await self.populate_programmatic_page(self.response.interaction)

        print(hash_, "run_page() current page=", current_page)

        generator_or_coroutine = current_page.func(self.response.interaction, self.custom_id.component_custom_id if self.custom_id else None)

        # if this is a programmatic page, we need to run it first
        if current_page.programmatic:
            if hasattr(generator_or_coroutine, "__anext__"):
                async for generator_response in generator_or_coroutine:
                    if not generator_response:
                        continue

                    if isinstance(generator_response, PromptPageData):
                        page_details = generator_response
                        # break
                    else:
                        yield generator_response
                        # await generator_response
                # await generator_or_coroutine.__anext__() # usually a response builder object
                # page_details: PromptPageData = await generator_or_coroutine.__anext__() # actual page details
            else:
                page_details: PromptPageData = await generator_or_coroutine

            current_page.details = page_details
            built_page = self.build_page(self.command_name, self.response.user_id, current_page, custom_id_data, hash_)

            # this stops the page from being sent if the user has already moved on
            if current_page.page_number != self.current_page_number or current_page.edited:
                return

            # prompt() requires below send_first, but entry_point() doesn't since it calls other functions
            yield await self.response.send_first(embed=built_page.embed, components=built_page.components, edit_original=True)
            return

        print(hash_, "building page run_page(), current page=", current_page)

        built_page = self.build_page(self.command_name, self.response.user_id, current_page, custom_id_data, hash_)

        print(hash_, "run_page() built page", built_page)

        if built_page.page_number != self.current_page_number:
            return

        yield await self.response.send_first(embed=built_page.embed, components=built_page.components, edit_original=True)

        # if current_page.programmatic:
        #     return

        if not current_page.programmatic:
            if hasattr(generator_or_coroutine, "__anext__"):
                async for generator_response in generator_or_coroutine:
                    if generator_response:
                        yield generator_response
            else:
                async_result = await generator_or_coroutine
                if async_result:
                    yield async_result


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

        return await self.run_page().__anext__()

    async def next(self, content: str=None):
        """Go to the next page of the prompt."""

        self.current_page_number += 1

        # await self.populate_programmatic_page(self.response.interaction)

        # built_page = self.build_page(self.command_name, self.response.user_id, self.pages[self.current_page_number])

        # return await self.response.send_first(content=content, embed=built_page.embed, components=built_page.components, edit_original=True)
        return await self.run_page().__anext__()

    async def go_to(self, page: Callable, content: str=None):
        """Go to a specific page of the prompt."""

        # print("go_to() called")

        for this_page in self.pages:
            if this_page.func == page:
                self.current_page_number = this_page.page_number
                # print("setting page number to", this_page.page_number)
                break
        else:
            raise PageNotFound(f"Page {page} not found.")

        # print("go_to() 1", self.response.responded, self.pages[self.current_page_number].details)

        # await self.populate_programmatic_page(self.response.interaction)

        # print("go_to() 2", self.current_page_number, self.response.responded, self.pages[self.current_page_number].details)

        # built_page = self.build_page(self.command_name, self.response.user_id, self.pages[self.current_page_number])
        # print("go_to() 3", self.current_page_number, self.response.responded)
        # print(built_page.embed, built_page.components)

        # return await self.response.send_first(content=content, embed=built_page.embed, components=built_page.components, edit_original=True)

        hash_ = uuid.uuid4().hex
        print("go_to() hash=", hash_)

        return await self.run_page(hash_=hash_).__anext__()

        # async for generator_response in self.run_page():
        #     print("generator_response go_to()", generator_response)
        #     yield generator_response

    async def finish(self, content: str = "Finished prompt.", embed: hikari.Embed = None, components: list[hikari.ActionRowComponent] = None):
        """Finish the prompt."""

        current_page = self.pages[self.current_page_number]

        current_page.edited = True

        return await self.response.send_first(content=content, embed=embed, components=components, edit_original=True)

    async def edit_component(self, **component_data):
        """Edit a component on the current page."""

        hash_ = uuid.uuid4().hex
        print("edit_component() hash=", hash_)

        current_page = self.pages[self.current_page_number]

        if current_page.programmatic:
            await self.populate_programmatic_page(self.response.interaction)

        for component in current_page.details.components:
            for component_custom_id, kwargs in component_data.items():
                if component.component_id == component_custom_id:
                    for attr_name, attr_value in kwargs.items():
                        if attr_name == "component_id":
                            component.component_id = attr_value
                        else:
                            setattr(component, attr_name, attr_value)

        built_page = self.build_page(self.command_name, self.response.user_id, current_page, hash_=hash_)

        # current_page.details = built_page
        # current_page.unparsed_programmatic = False
        current_page.edited = True

        return await self.response.send_first(embed=built_page.embed, components=built_page.components, edit_original=True)
