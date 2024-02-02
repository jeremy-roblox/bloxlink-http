from bloxlink_lib import fetch

from resources.exceptions import RobloxAPIError, RobloxNotFound
from resources.api.roblox.roblox_entity import RobloxEntity

ASSET_API = "https://economy.roblox.com/v2/assets"


class RobloxAsset(RobloxEntity):
    """Representation of an Asset on Roblox."""

    async def sync(self):
        """Load asset data from Roblox, specifically the name and description."""
        if self.synced:
            return

        if self.name is None or self.description is None:
            json_data, _ = await fetch("GET", f"{ASSET_API}/{self.id}/details")

            self.name = json_data.get("Name")
            self.description = json_data.get("Description")

            self.synced = True

    def __str__(self) -> str:
        name = f"**{self.name}**" if self.name else "*(Unknown Asset)*"
        return f"{name} ({self.id})"


async def get_asset(asset_id: str) -> RobloxAsset:
    """Get and sync an asset from Roblox.

    Args:
        asset_id (str): ID of the asset.

    Raises:
        RobloxNotFound: Raises RobloxNotFound when the Roblox API has an error.

    Returns:
        RobloxAsset: A synced roblox asset.
    """
    asset: RobloxAsset = RobloxAsset(id=asset_id)

    try:
        await asset.sync()  # this will raise if the asset doesn't exist
    except RobloxAPIError as exc:
        raise RobloxNotFound("This asset does not exist.") from exc

    return asset
