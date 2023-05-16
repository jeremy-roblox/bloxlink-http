from datetime import datetime
from resources.component_helper import get_custom_id_data
from resources.bloxlink import instance as bloxlink
import hikari


class Paginator:
    def __init__(
        self,
        guild_id,
        user_id,
        items,
        page_number=0,
        max_items=10,
        custom_formatter=None,
        extra_custom_ids="",
        item_filter=None,
    ):
        self.guild_id = guild_id
        self.user_id = user_id
        self.page_number = page_number
        self.items = items if not item_filter else item_filter(items)
        self.max_items = max_items
        self.custom_formatter = custom_formatter
        self.extra_custom_ids = extra_custom_ids

    @property
    async def embed(self):
        offset = self.page_number * self.max_items
        max_items = (
            len(self.items) if (offset + self.max_items >= len(self.items)) else offset + self.max_items
        )
        current_items = self.items[offset:max_items]

        if self.custom_formatter:
            embed = await self.custom_formatter(self.page_number, current_items, self.guild_id)
        else:
            embed = hikari.Embed(title=f"Test Pagination", description=f"Page {self.page_number}")

        return embed

    @embed.setter
    def embed(self, value):
        self._embed = value

    @property
    def components(self):
        button_row = bloxlink.rest.build_message_action_row()

        offset = self.page_number * self.max_items
        max_items = (
            len(self.items) if (offset + self.max_items >= len(self.items)) else offset + self.max_items
        )

        # Previous button
        button_row.add_interactive_button(
            hikari.ButtonStyle.SECONDARY,
            f"viewbinds:{self.user_id}:{self.page_number-1}:{self.extra_custom_ids}",
            label="\u2B9C",
            is_disabled=True if self.page_number == 0 else False,
        )

        # Next button
        button_row.add_interactive_button(
            hikari.ButtonStyle.SECONDARY,
            f"viewbinds:{self.user_id}:{self.page_number+1}:{self.extra_custom_ids}",
            label="\u2B9E",
            is_disabled=True if max_items == len(self.items) else False,
        )

        return button_row

    @components.setter
    def components(self, value):
        self._components = value
