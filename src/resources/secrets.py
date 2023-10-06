from os import environ as env

try:
    import config
except ImportError:
    config = None

VALID_SECRETS = (
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
    "BOT_API",
    "BOT_API_AUTH",
    "SERVER_HOST",
    "SERVER_PORT",
    "SERVER_AUTH",
)

for secret in VALID_SECRETS:
    globals()[secret] = env.get(secret) or getattr(config, secret, "")
