# fmt: off
MODULES = [
	"commands",
    "resources",
    "web.endpoints",
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

# Utilized for bind command logic.
GROUP_RANK_CRITERIA = {
    "equ": "Rank must exactly match...",
    "gte": "Rank must be greater than or equal to...",
    "lte": "Rank must be less than or equal to...",
    "rng": "Rank must be between or equal to two other ranks...",
    "gst": "User must NOT be a member of this group.",
    "all": "User must be a member of this group.",
}
GROUP_RANK_CRITERIA_TEXT = {
    "equ": "People with the rank",
    "gte": "People with a rank greater than or equal to",
    "lte": "People with a rank less than or equal to",
    "rng": "People with a rank between",
    "gst": "People who are not in **this group**",
    "all": "People who are in **this group**",
}
