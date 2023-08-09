from abc import ABC, abstractmethod, abstractproperty
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
