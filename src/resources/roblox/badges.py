from dataclasses import dataclass

from resources.exceptions import RobloxAPIError, RobloxNotFound
from resources.models import PartialMixin
from resources.utils import fetch

from .roblox_entity import RobloxEntity

BADGE_API = "https://badges.roblox.com/v1/badges"


@dataclass(slots=True)
class RobloxBadge(PartialMixin, RobloxEntity):
    async def sync(self):
        """Load badge data from Roblox, specifically the name and description."""
        if self.synced:
            return

        if self.name is None or self.description is None:
            json_data, _ = await fetch("GET", f"{BADGE_API}/{self.id}")

            self.name = json_data.get("name")
            self.description = json_data.get("description")

            self.synced = True

    def __str__(self) -> str:
        name = f"**{self.name}**" if self.name else "*(Unknown Badge)*"
        return f"{name} ({self.id})"


async def get_badge(badge_id: str) -> RobloxBadge:
    """Get and sync a badge from Roblox.

    Args:
        badge_id (str): ID of the badge.

    Raises:
        RobloxNotFound: Raises RobloxNotFound when the Roblox API has an error.

    Returns:
        RobloxGroup: A synced roblox badge.
    """
    badge: RobloxBadge = RobloxBadge(id=badge_id)

    try:
        await badge.sync()  # this will raise if the badge doesn't exist
    except RobloxAPIError:
        raise RobloxNotFound("This badge does not exist.")

    return badge
