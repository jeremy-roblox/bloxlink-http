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
    my_role: dict[str, int | str] = None

    async def sync(self):
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

    @property
    def logical_name(self):
        if self.name is None:
            return f"*(Unknown Group)* ({self.id})"
        else:
            return f"**{self.name}** ({self.id})"

    def roleset_name_string(self, id: int, bold_name=True, include_id=True) -> str:
        roleset_name = self.rolesets.get(id, "")
        if not roleset_name:
            return str(id)

        if bold_name:
            roleset_name = f"**{roleset_name}**"

        return f"{roleset_name} ({id})" if include_id else roleset_name


async def get_group(group_id: str) -> RobloxGroup:
    group: RobloxGroup = RobloxGroup(id=group_id)

    try:
        await group.sync()  # this will raise if the group doesn't exist
    except RobloxAPIError:
        raise RobloxNotFound("This group does not exist.")

    return group
