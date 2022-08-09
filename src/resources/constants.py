MODULES = [
	'commands',
    'resources'
]

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000

LIMITS = {
    "BINDS": {
        "FREE": 60,
        "PREMIUM": 200
    },
    "BACKUPS": 4,
    "RESTRICTIONS": {
        "FREE": 25,
        "PREMIUM": 250
    }
}

ALL_USER_API_SCOPES = ["groups", "badges"]
