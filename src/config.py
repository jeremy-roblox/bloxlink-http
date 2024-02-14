from typing import Literal
from dotenv import load_dotenv, dotenv_values
from pydantic import Field
from bloxlink_lib import BaseModel


load_dotenv()


class Config(BaseModel):
    """Type definition for config values."""

    #############################
    DISCORD_APPLICATION_ID: str
    DISCORD_TOKEN: str
    DISCORD_PUBLIC_KEY: str
    BOT_RELEASE: Literal["LOCAL", "MAIN", "PRO"] = "LOCAL"
    #############################
    MONGO_URL: str
    PROXY_URL: str = None
    MONGO_CA_FILE: str = None
    # these are optional because we can choose to use REDIS_URL or REDIS_HOST/REDIS_PORT/REDIS_PASSWORD
    REDIS_URL: str = None
    REDIS_HOST: str = None
    REDIS_PORT: str = None
    REDIS_PASSWORD: str = None
    #############################
    BIND_API: str
    BIND_API_AUTH: str
    BIND_API_NEW: str
    #############################
    SERVER_HOST: str
    SERVER_PORT: int = Field(default=8010)
    SERVER_AUTH: str
    #############################
    ROBLOX_INFO_SERVER: str
    #############################

    def model_post_init(self, __context):
        # easier to validate with python expressions instead of attrs validators
        if self.REDIS_URL is None and (
            self.REDIS_HOST is None or self.REDIS_PORT is None
        ):
            raise ValueError("REDIS_URL or REDIS_HOST/REDIS_PORT/REDIS_PASSWORD must be set")

        if all([self.REDIS_HOST, self.REDIS_PORT, self.REDIS_PASSWORD, self.REDIS_URL]):
            raise ValueError("REDIS_URL and REDIS_HOST/REDIS_PORT/REDIS_PASSWORD cannot both be set")



CONFIG: Config = Config(**dotenv_values())
