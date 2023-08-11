from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True)
class RobloxEntity(ABC):
    """Representation of an entity on Roblox."""

    id: str
    name: str = None
    description: str = None
    synced: bool = False

    @abstractmethod
    async def sync(self):
        """Sync a Roblox entity with the data from Roblox."""
        return

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
            from resources.roblox.assets import RobloxAsset

            return RobloxAsset(entity_id)

        case "badge":
            from resources.roblox.badges import RobloxBadge

            return RobloxBadge(entity_id)

        case "gamepass":
            from resources.roblox.gamepasses import RobloxGamepass

            return RobloxGamepass(entity_id)

        case "group":
            from resources.roblox.groups import RobloxGroup

            return RobloxGroup(entity_id)
