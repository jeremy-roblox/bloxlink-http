MODULES = [
	"commands",
    "resources"
]

ALL_USER_API_SCOPES = ["groups", "badges"]

DEFAULTS = {
    "nicknameTemplate": "{smart-name}"
}

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

SKU_TIERS = {
	"1022662272188952627": "basic/month"
}

ALL_USER_API_SCOPES = ["groups", "badges"]

RED_COLOR       = 0xdb2323
INVISIBLE_COLOR = 0x36393E

REPLY_EMOTE = "<:Reply:870665583593660476>"
REPLY_CONT = "<:ReplyCont:870764844012412938>"

UNICODE_LEFT = "\u276E"
UNICODE_RIGHT = "\u276F"
UNICODE_BLANK = "\u2800"

# Obscure unicode character, counts as 2 chars for length.
# Useful for custom_ids where user input is included but we need to split.
SPLIT_CHAR = "\U0001D15D"
