import aiohttp
from constants import SKILLS, PROFILE_MID_LINK, SKILLS_EMOJI, WEBSITE_LINK, SEARCH_PROFILE_LINK
from database import update_skills
import urllib.parse
import discord


async def lookup_profile(conn, input):
  c = await conn.cursor()
  async with aiohttp.ClientSession() as session, session.get(
      PROFILE_MID_LINK + input) as response:
    if response.status != 200:
      print(f"Searched for name: {input}")
      data = await profile_finder(session, input)
    else:
      data = await response.json()

  if data is None:
    return None

  levels = data.get('levels', None)
  if levels is None:
    return None

  (total_levels, total_skills) = total_stats(levels)

  #Update Skills in leaderboard:
  try:
    await update_skills(c, data, total_levels, total_skills)
    await conn.commit()
  except Exception as e:
    print(f"Error updating skills for {input}: {e}")

  return data, total_levels, total_skills


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


#Finds profile info from string vs ID
async def profile_finder(session, input):
  encoded_input = urllib.parse.quote(input)
  async with session.get(SEARCH_PROFILE_LINK + encoded_input) as search_response:
    search_json = await search_response.json()
    for profile in search_json:
      if profile['username'] == input:
        return profile
      for wallet in profile['cryptoWallets']:
        if wallet['address'] == input:
          return profile
    if search_json:
      return search_json[0]
    else:
      async with session.get(PROFILE_MID_LINK + input) as profile_response:
        if profile_response.status != 200:
          return None
        return await profile_response.json()


async def get_accounts_usernames(limiter, mids):
  link = 'https://pixels-server.pixels.xyz/v1/player/usernames?'
  extension = ''
  for mid in mids:
    extension += f'mid={mid}&'
  async with limiter, aiohttp.ClientSession() as session, session.get(
      link + extension) as response:
    return await response.json()
