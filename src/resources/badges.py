from dataclasses import dataclass
from .models import PartialMixin
from .utils import fetch
from .exceptions import RobloxNotFound, RobloxAPIError


BADGE_API = "https://badges.roblox.com/v1/badges"


@dataclass(slots=True)
class RobloxBadge(PartialMixin):
    id: str
    name: str = None
    description: str = None
    synced: bool = False

    async def sync(self):
        if self.name is None or self.description is None:
            json_data, _ = await fetch("GET", f"{BADGE_API}/{self.id}")

            self.name = json_data.get("name")
            self.description = json_data.get("description")

            self.synced = True


async def get_badge(badge_id: str) -> RobloxBadge:
    badge: RobloxBadge = RobloxBadge(id=badge_id)

    try:
        await badge.sync()  # this will raise if the badge doesn't exist
    except RobloxAPIError:
        raise RobloxNotFound("This badge does not exist.")

    return badge
