import discord 
import aiosqlite
import aiohttp
from constants import RequirementType
from database import get_discord_roles, get_guild_handle
from profile_utils import lookup_profile
from guild import guild_data

async def linkRole(interaction: discord.Interaction, role: discord.Role, requirement: str, quantity: str):
    if not interaction.guild:
        return
    guild_id = str(interaction.guild.id)
    role_id = str(role.id)

    async with aiosqlite.connect('discord.db') as db:
        # Fetch existing data for the guild
        async with db.execute('SELECT role_ids, role_requirements, role_numbers FROM discord_servers WHERE server_id = ?', (guild_id,)) as cursor:
            row = await cursor.fetchone()

        if row:
            role_ids, role_requirements, role_numbers = row
            role_ids_list = role_ids.split(' ') if role_ids else []
            role_requirements_list = role_requirements.split(' ') if role_requirements else []
            role_numbers_list = role_numbers.split(' ') if role_numbers else []

            if role_id in role_ids_list:
                index = role_ids_list.index(role_id)
                role_requirements_list[index] = requirement
                role_numbers_list[index] = quantity
            else:
                role_ids_list.append(role_id)
                role_requirements_list.append(requirement)
                role_numbers_list.append(quantity)

            role_ids = ' '.join(role_ids_list)
            role_requirements = ' '.join(role_requirements_list)
            role_numbers = ' '.join(role_numbers_list)
        else:
            role_ids = role_id
            role_requirements = requirement
            role_numbers = quantity

        # Insert or replace the data
        async with db.execute('SELECT 1 FROM discord_servers WHERE server_id = ?', (guild_id,)) as cursor:
            exists = await cursor.fetchone()

            if exists:
                if role_ids:
                    await db.execute('UPDATE discord_servers SET role_ids = ? WHERE server_id = ?', (role_ids, guild_id))
                if role_requirements:
                    await db.execute('UPDATE discord_servers SET role_requirements = ? WHERE server_id = ?', (role_requirements, guild_id))
                if role_numbers:
                    await db.execute('UPDATE discord_servers SET role_numbers = ? WHERE server_id = ?', (role_numbers, guild_id))
            else:
                # Insert a new entry
                await db.execute('''
                    INSERT INTO discord_servers (server_id, role_ids, role_requirements, role_numbers)
                    VALUES (?, ?, ?, ?)
                ''', (guild_id, role_ids, role_requirements, role_numbers))
        await db.commit()
        await interaction.followup.send(f"Successfully created or updated requirements for the role: {role.mention}", ephemeral=True)\
        
async def check_eligibility(interaction: discord.Interaction, primary_id):
    server_id = None
    if interaction.guild is not None:
        server_id = interaction.guild.id
    role_data = await get_discord_roles(server_id)
    valid_roles = []
    if role_data and role_data[2] and role_data[6] and role_data[7] and role_data[8]:
        guild_handle = await get_guild_handle(role_data[2])
        async with aiohttp.ClientSession() as session: #, aiosqlite.connect('leaderboard.db') as c,:
            guild_info = None
            if guild_handle is not None:
                guild_info = await guild_data(session, guild_handle[0])
            #player_data = await lookup_profile(c, primary_id)
            #await c.commit()
            
        role_ids = role_data[6].split(' ')
        role_requirements = role_data[7].split(' ')
        role_numbers = role_data[8].split(' ')
        for i in range(len(role_ids)):
            role_id = role_ids[i]
            format = role_requirements[i].split('+')
            isValid = False
            if guild_info is not None:
                isValid = check_guild_conditions(guild_info["guildMembers"], primary_id, format, role_numbers[i])
            if isValid:
                valid_roles.append(role_id)
    else: 
        print(f"invalid role data {role_data} for server {server_id}")

    return valid_roles

def check_guild_conditions(data, player_id, role_requirements, quantity):
    requirement = role_requirements[0].split("_")
    for item in data:
        player = item.get("player", {})
        role = item.get("role", None)
        if (player.get("_id") == player_id) and (role == requirement[1]) and (float(item.get(role_requirements[1], '-inf')) >= float(quantity)):
            print(f"Found role for player {player_id} | {role} | {float(quantity)}\n")
            return True
    return False