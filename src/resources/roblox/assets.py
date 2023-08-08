from dataclasses import dataclass

from .exceptions import RobloxAPIError, RobloxNotFound
from .models import PartialMixin
from .utils import fetch

ASSET_API = "https://economy.roblox.com/v2/assets"


@dataclass(slots=True)
class RobloxAsset(PartialMixin):
    id: str
    name: str = None
    description: str = None
    synced: bool = False

    async def sync(self):
        if self.name is None or self.description is None:
            json_data, _ = await fetch("GET", f"{ASSET_API}/{self.id}/details")

            self.name = json_data.get("Name")
            self.description = json_data.get("Description")

            self.synced = True


async def get_asset(asset_id: str) -> RobloxAsset:
    asset: RobloxAsset = RobloxAsset(id=asset_id)

    try:
        await asset.sync()  # this will raise if the asset doesn't exist
    except RobloxAPIError:
        raise RobloxNotFound("This asset does not exist.")

    return asset
