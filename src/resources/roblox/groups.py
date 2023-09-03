import re
from dataclasses import dataclass

from resources.exceptions import RobloxAPIError, RobloxNotFound
from resources.models import PartialMixin
from resources.utils import fetch

from .roblox_entity import RobloxEntity

GROUP_API = "https://groups.roblox.com/v1/groups"
ROBLOX_GROUP_REGEX = re.compile(r"roblox.com/groups/(\d+)/")


@dataclass(slots=True)
class RobloxGroup(PartialMixin, RobloxEntity):
    member_count: int = None
    rolesets: dict[int, str] = None
    user_roleset: dict = None

    async def sync(self):
        """Retrieve the roblox group information, consisting of rolesets, name, description, and member count."""
        if self.synced:
            return

        if self.rolesets is None:
            json_data, _ = await fetch("GET", f"{GROUP_API}/{self.id}/roles")

            self.rolesets = {int(roleset["rank"]): roleset["name"].strip() for roleset in json_data["roles"]}

        if self.name is None or self.description is None or self.member_count is None:
            json_data, _ = await fetch("GET", f"{GROUP_API}/{self.id}")

            self.name = json_data.get("name")
            self.description = json_data.get("description")
            self.member_count = json_data.get("memberCount")

            if self.rolesets is not None:
                self.synced = True

    def __str__(self) -> str:
        name = f"**{self.name}**" if self.name else "*(Unknown Group)*"
        return f"{name} ({self.id})"

    def roleset_name_string(self, roleset_id: int, bold_name=True, include_id=True) -> str:
        """Generate a nice string for a roleset name with failsafe capabilities.

        Args:
            roleset_id (int): ID of the Roblox roleset.
            bold_name (bool, optional): Wraps the name in ** when True. Defaults to True.
            include_id (bool, optional): Includes the ID in parenthesis when True. Defaults to True.

        Returns:
            str: The roleset string as requested.
        """
        roleset_name = self.rolesets.get(roleset_id, "")
        if not roleset_name:
            return str(roleset_id)

        if bold_name:
            roleset_name = f"**{roleset_name}**"

        return f"{roleset_name} ({roleset_id})" if include_id else roleset_name


async def get_group(group_id: str) -> RobloxGroup:
    """Get and sync a RobloxGroup.

    Args:
        group_id (str): ID of the group to retrieve

    Raises:
        RobloxNotFound: Raises RobloxNotFound when the Roblox API has an error.

    Returns:
        RobloxGroup: A synced roblox group.
    """
    group: RobloxGroup = RobloxGroup(id=group_id)

    try:
        await group.sync()  # this will raise if the group doesn't exist
    except RobloxAPIError:
        raise RobloxNotFound("This group does not exist.")

    return group
