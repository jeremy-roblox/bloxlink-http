from dataclasses import dataclass
from .models import PartialMixin


@dataclass(slots=True)
class RobloxGroup(PartialMixin):
    id: str
    name: str = None
    rolesets: dict = None
    my_role: dict = None


    async def sync(self):
       raise NotImplementedError()
