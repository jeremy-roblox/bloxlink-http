import snowfin
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient as MongoClient
from os import environ as env
from ..secrets import MONGO_URL

loop = asyncio.get_event_loop()

class Bloxlink(snowfin.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.mongo = MongoClient(env.get("MONGO_URL", MONGO_URL))

    @staticmethod
    def log(*args):
        print(args) # FIXME
        pass

    @staticmethod
    def error(*args, **kwargs):
        print(args, kwargs) # FIXME
        pass