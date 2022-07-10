from dataclasses import dataclass
from .models import PartialMixin
from .utils import fetch


GROUP_API = "https://groups.roblox.com/v1/groups"


@dataclass(slots=True)
class RobloxGroup(PartialMixin):
    id: str
    name: str = None
    rolesets: dict[str, int] = None
    my_role: dict[str, int] = None

    async def sync(self):
        if self.rolesets is None:
            json_data, _ = await fetch(f"{GROUP_API}/{self.id}/roles")

            self.rolesets = {
                roleset["name"].strip(): int(roleset["rank"]) for roleset in json_data["roles"]
            }
