from constants import GUILD_LINK, GUILD_HOME
import aiohttp
import aiosqlite
from database import init_guild_db
import discord
import time


async def assignGuild(interaction: discord.Interaction, guild_name: str):
    if interaction.guild is None:
        await interaction.followup.send(
            content=f"This command is for servers only!", ephemeral=True)
        return
    async with aiohttp.ClientSession() as session:
        data = await guild_data(session, guild_name)
        guild_info = data.get('guild', None)
        if guild_info is None:
            await interaction.followup.send(
                content=
                f"Could not find a guild with the handle @{guild_name}!",
                ephemeral=True)
            return
        guild_id = guild_info.get('_id', None)
        if guild_id is None:
            await interaction.followup.send(
                content=
                f"Could not find a guild ID with the handle @{guild_name}!",
                ephemeral=True)
            return
        await init_guild_db(guild_info, interaction.guild.id)
        await guild_update(data)
        await interaction.followup.send(
            f"Successfully assigned Pixels Guild {guild_name}!",
            ephemeral=True)


async def guild_data(session, guild_name):
    async with session.get(GUILD_LINK + guild_name) as response:
        return await response.json()


async def guild_update(guild_data):
    async with aiosqlite.connect('leaderboard.db') as conn:
        c = await conn.cursor()
        guild_data_batch = []
        guild_info = guild_data.get('guild', None)
        if guild_info is None:
            return None
        guild_id = guild_info.get('_id', None)
        if guild_id is None:
            return None
        members = guild_data.get('guildMembers', None)
        if members is None:
            print(f"Unable to update guild members for {guild_id}")
            return None
        for member in members:
            if member['role'] == 'Watcher':  # or member['role'] == 'Supporter'
                continue
            else:
                guild_data_batch.append(
                    (member['player']['_id'], member['player']['username'],
                     member['role']))

        # Fetch current members in the database
        result = await c.execute(f"SELECT user_id FROM guild_{guild_id}")
        current_members = await result.fetchall()

        current_member_ids = {row[0] for row in current_members}
        new_member_ids = {member[0] for member in guild_data_batch}
        members_to_remove = current_member_ids - new_member_ids

        # Remove members who have left the guild from the database
        if members_to_remove:
            await c.executemany(
                f"DELETE FROM guild_{guild_id} WHERE user_id = ?",
                [(member_id, ) for member_id in members_to_remove])

        await c.executemany(
            f'''INSERT OR REPLACE INTO guild_{guild_id} (user_id, username, role)
            VALUES (?, ?, ?)''', guild_data_batch)

        await conn.commit()
        return new_member_ids


async def all_guilds_data(update_set):
    i = 1
    while True:
        i += 20
        async with aiohttp.ClientSession() as session, session.get(
                GUILD_HOME + str(i)) as response:
            if response.status != 200:
                print(f'Guild Page {i-1} response not found:')
                time.sleep(1)
                i += 1
                continue

            data = await response.json()
            if not data.get('guilds', None):
                print(f'all_guilds_data() terminated at page: {i-1}')
                return

            for guild in data['guilds']:
                guild_handle = guild.get('handle', None)
                if guild_handle is None:
                    print('No guild handle found')
                    continue
                time.sleep(.2)

                new_data = await guild_data(session, guild_handle)
                await init_guild_db(new_data.get('guild', None))
                members = await guild_update(new_data)
                if members is None:
                    print('No members found')
                    continue

                for user_id in members:
                    if user_id not in update_set:
                        update_set.add(user_id)
                        print(f'Added User ID {user_id} to update set')


async def batch_assigned_guilds_update(update_set):
    async with aiosqlite.connect(
            'leaderboard.db') as conn, conn.execute_fetchall(
                'SELECT id FROM guilds') as execute:
        for id in execute:
            guild_id = id[0]
            async with conn.execute_fetchall(
                    f'SELECT user_id FROM guild_{guild_id}') as guild_users:
                for user in guild_users:
                    user_id = user[0]
                    if user_id not in update_set:
                        update_set.add(user_id)
