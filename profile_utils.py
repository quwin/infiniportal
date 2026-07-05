import re
import urllib.parse

import aiohttp
import discord

from constants import (
    PROFILE_MID_LINK,
    SEARCH_PROFILE_LINK,
    SKILLS,
    SKILLS_EMOJI,
    WEBSITE_LINK,
)
from database import find_cached_player, update_skills

def looks_like_object_id(value: str) -> bool:
    return bool(re.fullmatch(r"[a-fA-F0-9]{24}", value))

async def lookup_profile(conn, input):
    normalized_input = str(input).strip()

    async with aiohttp.ClientSession() as session:
        data = await fetch_profile_by_mid(session, normalized_input)
        if data is None:
            data = await profile_finder(session, normalized_input)

    if data is None:
        return None

    levels = data.get("levels")
    if levels is None:
        return None

    total_levels, total_skills = total_stats(levels)

    try:
        await update_skills(conn, data, total_levels, total_skills)
    except Exception as e:
        print(f"Error updating skills for {normalized_input}: {e}")

    return data, total_levels, total_skills


async def fetch_profile_by_mid(session, player_id: str):
    if not looks_like_object_id(player_id):
        return None

    async with session.get(PROFILE_MID_LINK + urllib.parse.quote(player_id)) as response:
        if response.status != 200:
            return None

        try:
            data = await response.json()
        except Exception as e:
            print(f"Profile MID JSON parse error for {player_id}: {e}")
            return None

    if isinstance(data, dict) and data.get("_id"):
        return data

    return None


async def profile_finder(session, input):
    normalized_input = str(input).strip()

    # Try upstream Pixels search.
    encoded_input = urllib.parse.quote(normalized_input)
    async with session.get(SEARCH_PROFILE_LINK + encoded_input) as search_response:
        try:
            search_json = await search_response.json()
        except Exception as e:
            print(f"Profile search JSON parse error for {normalized_input}: {e}")
            search_json = None

    if is_search_disabled_response(search_json):
        print(
            f"Pixels search disabled. Falling back to cached database search for: "
            f"{normalized_input}"
        )
        return await profile_from_cached_database(session, normalized_input)
    profile = extract_profile_from_search_response(search_json, normalized_input)
    if profile is not None:
        return profile
    # Final fallback: search your cached DB anyway.
    return await profile_from_cached_database(session, normalized_input)

def is_search_disabled_response(search_json) -> bool:
    if not isinstance(search_json, dict):
        return False

    return (
        search_json.get("codeName") == "SearchNotEnabled"
        or search_json.get("errorResponse", {}).get("codeName") == "SearchNotEnabled"
        or search_json.get("code") == 31082
        or search_json.get("errorResponse", {}).get("code") == 31082
    )


def extract_profile_from_search_response(search_json, input_value: str):
    if isinstance(search_json, dict):
        if search_json.get("_id") or search_json.get("username"):
            search_json = [search_json]
        else:
            print(f"Unexpected profile search response for {input_value}: {search_json}")
            return None

    if not isinstance(search_json, list):
        print(f"Unexpected profile search type for {input_value}: {type(search_json)}")
        return None

    for profile in search_json:
        if not isinstance(profile, dict):
            continue

        if profile.get("username") == input_value:
            return profile

        for wallet in profile.get("cryptoWallets", []):
            if wallet.get("address") == input_value:
                return profile

    if search_json and isinstance(search_json[0], dict):
        return search_json[0]

    return None


async def profile_from_cached_database(session, input_value: str):
    cached_player = await find_cached_player(input_value)

    if cached_player is None:
        return None

    player_id = cached_player["user_id"]

    async with session.get(PROFILE_MID_LINK + urllib.parse.quote(player_id)) as response:
        if response.status != 200:
            print(f"Cached player MID lookup failed for {player_id}: HTTP {response.status}")
            return None

        try:
            data = await response.json()
        except Exception as e:
            print(f"Cached player profile JSON parse error for {player_id}: {e}")
            return None

    if isinstance(data, dict) and data.get("_id"):
        return data

    return None


def total_stats(levels):
    total_level = 0
    total_exp = 0

    for skill in SKILLS:
        lvl_data = levels.get(skill)
        if lvl_data:
            total_level += lvl_data["level"]
            total_exp += lvl_data["totalExp"]

    return total_level, total_exp


def embed_profile(data, total_levels, total_skills):
    embed = discord.Embed(
        title=f"**{data['username']}**",
        description=f"**User ID**: `{data['_id']}`",
        color=0x00FF00,
    )

    embed.add_field(
        name=f"Account Level: {total_levels}",
        value=f"**Total Exp:** - {int(total_skills):,}",
        inline=False,
    )

    for i, skill in enumerate(SKILLS):
        skill_data = data["levels"].get(skill)
        if skill_data:
            embed.add_field(
                name=f"{SKILLS_EMOJI[i]} {skill.title()} - Lvl {skill_data['level']}",
                value=f"> {int(skill_data['totalExp']):,} xp",
                inline=True,
            )

    image_url = data.get("currentAvatar", {}).get("pieces", {}).get("image")

    if image_url:
        embed.set_thumbnail(url=image_url)

    embed.set_author(
        name="Infiniport.al Link",
        url=f"{WEBSITE_LINK}{data['_id']}",
    )

    return embed


async def get_accounts_usernames(limiter, mids):
    link = "https://pixels-server.pixels.xyz/v1/player/usernames?"
    extension = ""

    for mid in mids:
        extension += f"mid={mid}&"

    async with limiter, aiohttp.ClientSession() as session:
        async with session.get(link + extension) as response:
            return await response.json()