import snowfin
from motor.motor_asyncio import AsyncIOMotorClient as MongoClient
from os import environ as env
from resources.constants import MONGO_URL

class Bloxlink(snowfin.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.mongo = MongoClient(env.get("MONGO_URL", MONGO_URL))


