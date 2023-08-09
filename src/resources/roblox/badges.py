from dataclasses import dataclass

from resources.exceptions import RobloxAPIError, RobloxNotFound
from resources.models import PartialMixin
from resources.utils import fetch

from .roblox_entity import RobloxEntity

BADGE_API = "https://badges.roblox.com/v1/badges"


@dataclass(slots=True)
class RobloxBadge(PartialMixin, RobloxEntity):
    async def sync(self):
        if self.name is None or self.description is None:
            json_data, _ = await fetch("GET", f"{BADGE_API}/{self.id}")

            self.name = json_data.get("name")
            self.description = json_data.get("description")

            self.synced = True

    @property
    def logical_name(self):
        if self.name is None:
            return f"*(Unknown Badge)* ({self.id})"
        else:
            return f"**{self.name}** ({self.id})"


async def get_badge(badge_id: str) -> RobloxBadge:
    badge: RobloxBadge = RobloxBadge(id=badge_id)

    try:
        await badge.sync()  # this will raise if the badge doesn't exist
    except RobloxAPIError:
        raise RobloxNotFound("This badge does not exist.")

    return badge
