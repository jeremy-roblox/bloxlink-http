import math

import hikari

from resources.bloxlink import instance as bloxlink
from resources.component_helper import get_custom_id_data
from resources.constants import UNICODE_LEFT, UNICODE_RIGHT


class Paginator:
    def __init__(
        self,
        guild_id,
        user_id,
        items: list,
        source_cmd_name: str,
        page_number=0,
        max_items=10,
        custom_formatter=None,
        component_generation=None,
        extra_custom_ids="",
        item_filter=None,
        include_cancel_button=False,
    ):
        self.guild_id = guild_id
        self.user_id = user_id

        self.page_number = page_number
        self.source_cmd_name = source_cmd_name

        self.items = items if not item_filter else item_filter(items)
        self.max_pages = math.ceil(len(self.items) / max_items)
        self.max_items = max_items

        self.custom_formatter = custom_formatter
        self.component_generation = component_generation

        self.extra_custom_ids = extra_custom_ids
        self.include_cancel_button = include_cancel_button

    def _get_current_items(self):
        offset = self.page_number * self.max_items
        max_items = (
            len(self.items) if (offset + self.max_items >= len(self.items)) else offset + self.max_items
        )
        return self.items[offset:max_items]

    @property
    async def embed(self):
        current_items = self._get_current_items()

        if self.custom_formatter:
            embed = await self.custom_formatter(
                self.page_number, current_items, self.guild_id, self.max_pages
            )
        else:
            embed = hikari.Embed(title=f"Test Pagination", description=f"Page {self.page_number}")

        self._embed = embed
        return self._embed

    @embed.setter
    def embed(self, value):
        self._embed = value

    @property
    async def components(self) -> tuple:
        button_row = bloxlink.rest.build_message_action_row()

        # Previous button
        button_row.add_interactive_button(
            hikari.ButtonStyle.SECONDARY,
            f"{self.source_cmd_name}:page:{self.user_id}:{self.page_number-1}:{self.extra_custom_ids}",
            label=UNICODE_LEFT,
            is_disabled=self.page_number <= 0,
        )

        # Next button
        button_row.add_interactive_button(
            hikari.ButtonStyle.SECONDARY,
            f"{self.source_cmd_name}:page:{self.user_id}:{self.page_number+1}:{self.extra_custom_ids}",
            label=UNICODE_RIGHT,
            is_disabled=self.page_number + 1 >= self.max_pages,
        )

        if self.include_cancel_button:
            button_row.add_interactive_button(
                hikari.ButtonStyle.SECONDARY, f"{self.source_cmd_name}:cancel:{self.user_id}", label="Cancel"
            )

        component_output = []
        if self.component_generation:
            generated_components = await self.component_generation(
                self._get_current_items(),
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
