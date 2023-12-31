from abc import ABC, abstractmethod
from attrs import define
from typing import Literal


@define(slots=True)
class RobloxEntity(ABC):
    """Representation of an entity on Roblox.

    Attributes:
        id (str, optional): Roblox given ID of the entity.
        name (str, optional): Name of the entity.
        description (str, optional): The description of the entity (if any).
        synced (bool): If this entity has been synced with Roblox or not. False by default.
    """

    id: str
    name: str = None
    description: str = None
    synced: bool = False
    url: str = None

    @abstractmethod
    async def sync(self):
        """Sync a Roblox entity with the data from Roblox."""
        raise NotImplementedError()

    def __str__(self) -> str:
        name = f"**{self.name}**" if self.name else "*(Unknown Roblox Entity)*"
        return f"{name} ({self.id})"


def create_entity(
    category: Literal["asset", "badge", "gamepass", "group"] | str, entity_id: int
) -> RobloxEntity:
    """Create a respective Roblox entity from a category and ID.

    Args:
        category (str): Type of Roblox entity to make. Subset from asset, badge, group, gamepass.
        entity_id (int): ID of the entity on Roblox.

    Returns:
        RobloxEntity: The respective RobloxEntity implementer, unsynced.
    """
    match category:
        case "asset":
            from resources.roblox.assets import RobloxAsset  # pylint: disable=import-outside-toplevel

            return RobloxAsset(entity_id)

        case "badge":
            from resources.roblox.badges import RobloxBadge  # pylint: disable=import-outside-toplevel

            return RobloxBadge(entity_id)

        case "gamepass":
            from resources.roblox.gamepasses import RobloxGamepass  # pylint: disable=import-outside-toplevel

            return RobloxGamepass(entity_id)

        case "group":
            from resources.roblox.groups import RobloxGroup  # pylint: disable=import-outside-toplevel

            return RobloxGroup(entity_id)
