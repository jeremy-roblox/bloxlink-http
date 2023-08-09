from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class RobloxEntity(ABC):
    id: str
    name: str = None
    description: str = None
    synced: bool = False

    @abstractmethod
    async def sync(self):
        return

    @property
    def logical_name(self):
        if self.name is None:
            return f"*(Unknown Roblox Entity)* ({self.id})"
        else:
            return f"**{self.name}** ({self.id})"


def create_entity(category: str, entity_id: int) -> RobloxEntity:
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
