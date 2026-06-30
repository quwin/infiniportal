"""
Mock constants for portfolio/demo use.
This file replaces production URLs with local test endpoints.
"""

from enum import Enum
import os

# -----------------------------
# Demo credentials / secrets
# -----------------------------

TOKEN = os.getenv("DISCORD_TOKEN", "")
COLLAB_ID = os.getenv("COLLAB_ID", "")
COLLAB_SECRET = os.getenv("COLLAB_SECRET", "")
COLLAB_KEY = os.getenv("COLLAB_API_KEY", "")
WEBSITE_LINK = "https://infiniportal.quwin.dev/player"
SERVER_IP = os.getenv("SERVER_IP", "0.0.0.0")

# -----------------------------
# Local  API base
# -----------------------------

PROFILE_MID_LINK = "https://pixels-server.pixels.xyz/v1/player?mid="
SPECK_OWNER_LINK = "https://pixels-server.pixels.xyz/v1/infiniportal/farm_details/shareRent"
NFT_LAND_LINK = "https://pixels-server.pixels.xyz/v1/infiniportal/farm_details/pixelsNFTFarm-"
GUILD_LINK = "https://dashboard.pixels.xyz/guild/"
GUILD_HOME = "https://pixels-server.pixels.xyz/v1/guilds?page="
GUILD_EMBLEM = "https://dashboard.pixels.xyz/guild-emblem/"
REDIRECT_URI = "https://infiniportal.quwin.dev/callback"
SEARCH_PROFILE_LINK = "https://pixels-server.pixels.xyz/v1/player/search?input="

# -----------------------------
# App data
# -----------------------------

SKILLS = [
    "forestry",
    "woodwork",
    "farming",
    "cooking",
    "petcare",
    "exploration",
    "mining",
    "stoneshaping",
    "metalworking",
    "business",
]
SKILLS_EMOJI = [
    "🌲",
    "🪵",
    "🌾",
    "🍳",
    "🐾",
    "🧭",
    "⛏️",
    "🪨",
    "⚒️",
    "💼",
]

ICON = "https://d31ss916pli4td.cloudfront.net/game/ui/skills/skills_icon_"
ICON_END = ".png"


# -----------------------------
# Batch update settings
# -----------------------------

BATCH_SIZE = 25
GIVE_UP = 10
FIRST_SPECK = 1
SPECK_RATE = 0.2


# -----------------------------
# Discord slash-command enums
# -----------------------------

class SkillEnum(Enum):
    NONE = "total"
    FORESTRY = "forestry"
    WOODWORK = "woodwork"
    FARMING = "farming"
    COOKING = "cooking"
    PETCARE = "petcare"
    EXPLORATION = "exploration"
    MINING = "mining"
    STONESHAPING = "stoneshaping"
    METALWORKING = "metalworking"
    BUSINESS = "business"


class SortEnum(Enum):
    LEVEL = "level"
    EXP = "exp"


class RequirementType(Enum):
    PLEDGE = "pledge"
    OWN = "own"
    PLEDGE_LAND = "pledge_land"
    OWN_LAND = "own_land"
    LEVEL = "level"