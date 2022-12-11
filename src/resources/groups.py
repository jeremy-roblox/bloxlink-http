from dataclasses import dataclass
from .models import PartialMixin
from .utils import fetch
from .exceptions import BadArgument, RobloxNotFound, RobloxAPIError
import re


GROUP_API = "https://groups.roblox.com/v1/groups"
ROBLOX_GROUP_REGEX = re.compile(r"roblox.com/groups/(\d+)/")



@dataclass(slots=True)
class RobloxGroup(PartialMixin):
    id: str
    name: str = None
    description: str = None
    member_count: int = None
    rolesets: dict[str, int] = None
    my_role: dict[str, int | str] = None
    synced: bool = False

    async def sync(self):
        if self.rolesets is None:
            json_data, _ = await fetch("GET", f"{GROUP_API}/{self.id}/roles")

            self.rolesets = {
                roleset["name"].strip(): int(roleset["rank"]) for roleset in json_data["roles"]
            }

        if self.name is None or self.description is None or self.member_count is None:
            json_data, _ = await fetch("GET", f"{GROUP_API}/{self.id}")

            self.name = json_data.get("name")
            self.description = json_data.get("description")
            self.member_count = json_data.get("memberCount")

            if self.rolesets is not None:
                self.synced = True


async def get_group(group_id: str) -> RobloxGroup:
    group: RobloxGroup = RobloxGroup(id=group_id)
    await group.sync() # this will raise if the group doesn't exist

    return group