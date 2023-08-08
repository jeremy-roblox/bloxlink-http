from dataclasses import dataclass

from .exceptions import RobloxAPIError, RobloxNotFound
from .models import PartialMixin
from .utils import fetch

GAMEPASS_API = "https://economy.roblox.com/v1/game-pass"


@dataclass(slots=True)
class RobloxGamepass(PartialMixin):
    id: str
    name: str = None
    description: str = None
    synced: bool = False

    async def sync(self):
        if self.name is None or self.description is None:
            json_data, _ = await fetch("GET", f"{GAMEPASS_API}/{self.id}/game-pass-product-info")

            self.name = json_data.get("Name")
            self.description = json_data.get("Description")

            self.synced = True


async def get_gamepass(gamepass_id: str) -> RobloxGamepass:
    gamepass: RobloxGamepass = RobloxGamepass(id=gamepass_id)

    try:
        await gamepass.sync()  # this will raise if the gamepass doesn't exist
    except RobloxAPIError:
        raise RobloxNotFound("This gamepass does not exist.")

    return gamepass
