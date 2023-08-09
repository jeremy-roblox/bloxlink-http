from dataclasses import dataclass

from resources.exceptions import RobloxAPIError, RobloxNotFound
from resources.models import PartialMixin
from resources.utils import fetch

from .roblox_entity import RobloxEntity

ASSET_API = "https://economy.roblox.com/v2/assets"


@dataclass(slots=True)
class RobloxAsset(PartialMixin, RobloxEntity):
    async def sync(self):
        if self.name is None or self.description is None:
            json_data, _ = await fetch("GET", f"{ASSET_API}/{self.id}/details")

            self.name = json_data.get("Name")
            self.description = json_data.get("Description")

            self.synced = True

    @property
    def logical_name(self):
        if self.name is None:
            return f"*(Unknown Asset)* ({self.id})"
        else:
            return f"**{self.name}** ({self.id})"


async def get_asset(asset_id: str) -> RobloxAsset:
    asset: RobloxAsset = RobloxAsset(id=asset_id)

    try:
        await asset.sync()  # this will raise if the asset doesn't exist
    except RobloxAPIError:
        raise RobloxNotFound("This asset does not exist.")

    return asset
