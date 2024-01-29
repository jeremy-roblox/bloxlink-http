from typing import Literal
from bot_utils import RobloxEntity, RobloxGroup




def create_entity(
    category: Literal["asset", "badge", "gamepass", "group"] | str, entity_id: int
) -> RobloxEntity:
    """Create a respective Roblox entity from a category and ID.

    Args:
        category (str): Type of Roblox entity to make. Subset from asset, badge, group, gamepass.
        entity_id (int): ID of the entity on Roblox.

    Returns:
        RobloxEntity: The respective RobloxEntity implementer, unsynced.
    """
    match category:
        case "asset":
            from resources.api.roblox.assets import RobloxAsset  # pylint: disable=import-outside-toplevel

            return RobloxAsset(entity_id)

        case "badge":
            from resources.api.roblox.badges import RobloxBadge  # pylint: disable=import-outside-toplevel

            return RobloxBadge(entity_id)

        case "gamepass":
            from resources.api.roblox.gamepasses import RobloxGamepass  # pylint: disable=import-outside-toplevel

            return RobloxGamepass(entity_id)

        case "group":
            return RobloxGroup(entity_id)
