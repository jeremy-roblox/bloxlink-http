import hikari
from pydantic import Field
from bloxlink_lib import BaseModelArbitraryTypes


class InteractiveMessage(BaseModelArbitraryTypes):
    """Represents a prompt consisting of an embed & components for the message."""

    content: str = None
    embed: hikari.Embed = hikari.Embed()
    action_rows: list = Field(default_factory=list) # TODO: type this better
