from dataclasses import dataclass

from resources.exceptions import RobloxAPIError, RobloxNotFound
from resources.models import PartialMixin
from resources.utils import fetch

from .roblox_entity import RobloxEntity

GAMEPASS_API = "https://economy.roblox.com/v1/game-pass"


@dataclass(slots=True)
class RobloxGamepass(PartialMixin, RobloxEntity):
    async def sync(self):
        if self.name is None or self.description is None:
            json_data, _ = await fetch("GET", f"{GAMEPASS_API}/{self.id}/game-pass-product-info")

            self.name = json_data.get("Name")
            self.description = json_data.get("Description")

            self.synced = True

    @property
    def logical_name(self):
        if self.name is None:
            return f"*(Unknown Gamepass)* ({self.id})"
        else:
            return f"**{self.name}** ({self.id})"


async def get_gamepass(gamepass_id: str) -> RobloxGamepass:
    gamepass: RobloxGamepass = RobloxGamepass(id=gamepass_id)

    try:
        await gamepass.sync()  # this will raise if the gamepass doesn't exist
    except RobloxAPIError:
        raise RobloxNotFound("This gamepass does not exist.")

    return gamepass
