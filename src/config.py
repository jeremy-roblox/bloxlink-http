from typing import Literal
from dotenv import dotenv_values
from pydantic import Field
from bloxlink_lib import Config as BLOXLINK_CONFIG


class Config(BLOXLINK_CONFIG):
    """Type definition for config values."""

    #############################
    DISCORD_APPLICATION_ID: str
    DISCORD_PUBLIC_KEY: str
    BOT_RELEASE: Literal["LOCAL", "MAIN", "PRO"] = "LOCAL"
    #############################
    BIND_API: str
    BIND_API_AUTH: str
    BIND_API_NEW: str
    #############################
    SERVER_HOST: str
    SERVER_PORT: int = Field(default=8010)
    SERVER_AUTH: str
    #############################



CONFIG: Config = Config(**dotenv_values())
