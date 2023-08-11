from dataclasses import dataclass

from resources.exceptions import RobloxAPIError, RobloxNotFound
from resources.models import PartialMixin
from resources.utils import fetch

from .roblox_entity import RobloxEntity

GAMEPASS_API = "https://economy.roblox.com/v1/game-pass"


@dataclass(slots=True)
class RobloxGamepass(PartialMixin, RobloxEntity):
    async def sync(self):
        """Load gamepass data from Roblox, specifically the name and description."""
        if self.synced:
            return

        if self.name is None or self.description is None:
            json_data, _ = await fetch("GET", f"{GAMEPASS_API}/{self.id}/game-pass-product-info")

            self.name = json_data.get("Name")
            self.description = json_data.get("Description")

            self.synced = True

    def __str__(self) -> str:
        name = f"**{self.name}**" if self.name else "*(Unknown Gamepass)*"
        return f"{name} ({self.id})"


async def get_gamepass(gamepass_id: str) -> RobloxGamepass:
    """Get and sync a gamepass from Roblox.

    Args:
        gamepass_id (str): ID of the gamepass.

    Raises:
        RobloxNotFound: Raises RobloxNotFound when the Roblox API has an error.

    Returns:
        RobloxGroup: A synced roblox gamepass.
    """
    gamepass: RobloxGamepass = RobloxGamepass(id=gamepass_id)

    try:
        await gamepass.sync()  # this will raise if the gamepass doesn't exist
    except RobloxAPIError:
        raise RobloxNotFound("This gamepass does not exist.")

    return gamepass
