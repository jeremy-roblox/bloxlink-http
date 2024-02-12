import math
from typing import Callable

import hikari

from resources.bloxlink import instance as bloxlink
from resources.constants import UNICODE_LEFT, UNICODE_RIGHT


class Paginator[T]:
    """Dynamically create prompts that may require more than one embed to cleanly show data."""

    def __init__(
        self,
        guild_id: int,
        user_id: int,
        items: list[T],
        command_name: str,
        page_number: int=0,
        max_items: int=10,
        custom_formatter: Callable | None=None,
        component_generation: Callable | None=None,
        extra_custom_ids: str="",
        item_filter: Callable | None = None,
        include_cancel_button: bool=False,
    ):
        """Create a paginator handler.

        Args:
            guild_id: The ID of the guild where the command that required pagination was ran.
            user_id: The ID of the user who ran the command.
            items (list): The list of items that need to be paginated.
            command_name (str): The name of the command. Used for component custom IDs.
            page_number (int, optional): The current page number. Defaults to 0.
            max_items (int, optional): The maximum number of items per page. Defaults to 10.
            custom_formatter (Callable, optional): The formatter to use to style the embed. Defaults to None.
                Expects the arguments: (page_number: int, items: list, guild_id: int | str, max_pages: int)
                Where the items are only the items for this page.
            component_generation (Callable, optional): A function to generate the components that will be added
                to this prompt in addition to the page flip buttons. Defaults to None.
                Expects the arguments: (items: list, user_id: str | int, extra_custom_ids: str)
            extra_custom_ids (str, optional): This will be passed to the component_generation callable. Defaults to "".
                Used to provide additional information to the additional components dynamically.
            item_filter (Callable, optional): Callable used to filter the entire item list. Defaults to None.
            include_cancel_button (bool, optional): Optionally include a button to cancel this prompt. Defaults to False.
        """

        self.guild_id = guild_id
        self.user_id = user_id

        self.page_number = page_number
        self.command_name = command_name

        self.items = items if not item_filter else item_filter(items)
        self.max_pages = math.ceil(len(self.items) / max_items)
        self.max_items = max_items

        self.custom_formatter = custom_formatter
        self.component_generation = component_generation

        self.extra_custom_ids = extra_custom_ids
        self.include_cancel_button = include_cancel_button

    @property
    def current_items(self) -> list[T]:
        """Get the items that apply to this page number."""

        offset = self.page_number * self.max_items
        max_items = (
            len(self.items) if (offset + self.max_items >= len(self.items)) else offset + self.max_items
        )

        return self.items[offset:max_items]

    @property
    async def embed(self) -> hikari.Embed:
        """The embed that will be displayed to the user."""

        if self.custom_formatter:
            embed = await self.custom_formatter(
                self.page_number, self.current_items, self.guild_id, self.max_pages
            )
        else:
            embed = hikari.Embed(title="Test Pagination", description=f"Page {self.page_number}")

        self._embed = embed
        return self._embed

    @embed.setter
    def embed(self, value):
        self._embed = value

    @property
    async def components(self) -> tuple:
        """The components for this prompt as a tuple."""
        button_row = bloxlink.rest.build_message_action_row()

        # Previous button
        button_row.add_interactive_button(
            hikari.ButtonStyle.SECONDARY,
            f"{self.command_name}:page:{self.user_id}:{self.page_number-1}:{self.extra_custom_ids}",
            label=UNICODE_LEFT,
            is_disabled=self.page_number <= 0,
        )

        # Next button
        button_row.add_interactive_button(
            hikari.ButtonStyle.SECONDARY,
            f"{self.command_name}:page:{self.user_id}:{self.page_number+1}:{self.extra_custom_ids}",
            label=UNICODE_RIGHT,
            is_disabled=self.page_number + 1 >= self.max_pages,
        )

        if self.include_cancel_button:
            button_row.add_interactive_button(
                hikari.ButtonStyle.SECONDARY, f"{self.command_name}:cancel:{self.user_id}", label="Cancel"
            )

        component_output = []
        if self.component_generation:
            generated_components = await self.component_generation(
                self.current_items,
                self.user_id,
                self.extra_custom_ids,
            )

            if isinstance(generated_components, (list, tuple)):
                component_output.extend(generated_components)
            else:
                component_output.append(generated_components)

        component_output.append(button_row)
        self._components = tuple(component_output)

        return self._components

    @components.setter
    def components(self, value):
        self._components = value
