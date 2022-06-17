from os import environ as env

try:
    import config
except ImportError:
    config = None

VALID_SECRETS = (
    "DISCORD_PUBLIC_KEY", "MONGO_URL",
    "DISCORD_APPLICATION_ID", "DISCORD_TOKEN",
    "REDISHOST", "REDISPORT", "REDISPASSWORD",
    "PROXY_URL"
)

for secret in VALID_SECRETS:
    globals()[secret] = env.get(secret) or getattr(config, secret, "")
