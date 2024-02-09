from typing import Any
import hikari
from pydantic import Field
from bloxlink_lib import BaseModelArbitraryTypes


class InteractiveMessage(BaseModelArbitraryTypes):
    """Represents a prompt consisting of an embed & components for the message."""

    content: str | None = None
    embed: hikari.Embed | None = hikari.Embed()
    action_rows: list | None = Field(default_factory=list) # TODO: type this better

    embed_description: str | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.embed_description:
            if not self.embed:
                self.embed = hikari.Embed()

            self.embed.description = self.embed_description
