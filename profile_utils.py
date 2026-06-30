import aiohttp
from constants import SKILLS, PROFILE_MID_LINK, SKILLS_EMOJI, WEBSITE_LINK, SEARCH_PROFILE_LINK
from database import update_skills
import urllib.parse
import discord
import re


async def lookup_profile(conn, input):
    normalized_input = str(input).strip()

    async with aiohttp.ClientSession() as session:
        data = await fetch_profile_by_mid(session, normalized_input)

        # If the input looks like a Mongo/ObjectId player id, do not fall back
        # to the search endpoint. The search endpoint is for usernames/wallets.
        if data is None and not looks_like_object_id(normalized_input):
            print(f"Searched for name/wallet: {normalized_input}")
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


def looks_like_object_id(value: str) -> bool:
    return bool(re.fullmatch(r"[a-fA-F0-9]{24}", value))


async def fetch_profile_by_mid(session, player_id: str):
    async with session.get(PROFILE_MID_LINK + urllib.parse.quote(player_id)) as response:
        if response.status != 200:
            print(f"Profile MID lookup failed for {player_id}: HTTP {response.status}")
            return None

        try:
            data = await response.json()
        except Exception as e:
            print(f"Profile MID JSON parse error for {player_id}: {e}")
            return None

    if not isinstance(data, dict):
        print(f"Unexpected profile MID response for {player_id}: {data}")
        return None

    if data.get("_id") or data.get("username"):
        return data

    print(f"Profile MID response missing player fields for {player_id}: {data}")
    return None


async def profile_finder(session, input):
    encoded_input = urllib.parse.quote(input)

    async with session.get(SEARCH_PROFILE_LINK + encoded_input) as search_response:
        try:
            search_json = await search_response.json()
        except Exception as e:
            print(f"Profile search JSON parse error for {input}: {e}")
            return None

    if isinstance(search_json, dict):
        # If it is an actual single profile object, normalize it to a list.
        if "username" in search_json or "_id" in search_json:
            search_json = [search_json]
        else:
            print(f"Unexpected profile search response for {input}: {search_json}")
            return None

    if not isinstance(search_json, list):
        print(f"Unexpected profile search type for {input}: {type(search_json)}")
        return None

    for profile in search_json:
        if not isinstance(profile, dict):
            print(f"Unexpected profile entry for {input}: {profile}")
            continue

        if profile.get("username") == input:
            return profile

        for wallet in profile.get("cryptoWallets", []):
            if wallet.get("address") == input:
                return profile

    if search_json and isinstance(search_json[0], dict):
        return search_json[0]

    return None


def total_stats(levels):
  total_level = 0
  total_exp = 0
  for skill in SKILLS:
    lvl_data = levels.get(f'{skill}', None)
    if lvl_data:
      total_level += lvl_data['level']
      total_exp += lvl_data['totalExp']

  return total_level, total_exp


def embed_profile(data, total_levels, total_skills):
  embed = discord.Embed(title=f"**{data['username']}**",
                        description=f"**User ID**: `{data['_id']}`",
                        color=0x00ff00)

  embed.add_field(name=f"Account Level: {total_levels}",
                  value=f"**Total Exp:** - {'{:,}'.format(int(total_skills))}",
                  inline=False)

  # info for each Skill
  i = 0
  for skill in SKILLS:
    skill_data = data['levels'].get(f'{skill}', None)
    if skill_data:
      embed.add_field(
          name=f"{SKILLS_EMOJI[i]} {skill.title()} - Lvl {skill_data['level']}",
          value=f"> {'{:,}'.format(int(skill_data['totalExp']))} xp",
          inline=True)
    i += 1

  # Thumbnail image data
  image_url = data.get('currentAvatar', {}).get('pieces', {}).get('image', None)

  if image_url:
    embed.set_thumbnail(url=image_url)

  # Footer text
  embed.set_author(name="Infiniport.al Link", url=f"{WEBSITE_LINK}{data['_id']}")

  return embed

async def get_accounts_usernames(limiter, mids):
  link = 'https://pixels-server.pixels.xyz/v1/player/usernames?'
  extension = ''
  for mid in mids:
    extension += f'mid={mid}&'
  async with limiter, aiohttp.ClientSession() as session, session.get(
      link + extension) as response:
    return await response.json()
