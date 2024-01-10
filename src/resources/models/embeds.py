import hikari
from attrs import define, field


@define(slots=True)
class InteractiveMessage:
    """Represents a prompt consisting of an embed & components for the message."""

    content: str = None
    embed: hikari.Embed = hikari.Embed()
    action_rows: list = field(factory=list)
