from os import environ as env
from typing import Optional

try:
    import config
except ImportError:
    config = None

VALID_SECRETS = [
    "DISCORD_APPLICATION_ID",
    "DISCORD_TOKEN",
    "DISCORD_PUBLIC_KEY",
    "MONGO_URL",
    "PROXY_URL",
    "MONGO_CA_FILE",
    "REDIS_URL",
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_PASSWORD",
    "BIND_API",
    "BIND_API_AUTH",
    "SERVER_HOST",
    "SERVER_PORT",
    "SERVER_AUTH",
    "ROBLOX_INFO_SERVER",
    "BOT_RELEASE"
]

# Define type for secrets
Secret = Optional[str]


for secret in VALID_SECRETS:
    globals()[secret]: Secret = env.get(secret) or getattr(config, secret, "")
