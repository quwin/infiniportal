from constants import GUILD_LINK, GUILD_HOME
import aiohttp
from database import init_guild_db, replace_guild_members, fetch_all_assigned_guild_member_ids
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
    guild_info = guild_data.get("guild")
    if guild_info is None:
        return None

    guild_id = guild_info.get("_id")
    if guild_id is None:
        return None

    members = guild_data.get("guildMembers")
    if members is None:
        print(f"Unable to update guild members for {guild_id}")
        return None

    guild_data_batch = []

    for member in members:
        if member["role"] == "Watcher":
            continue

        guild_data_batch.append(
            (
                member["player"]["_id"],
                member["player"]["username"],
                member["role"],
            )
        )

    await replace_guild_members(guild_id, guild_data_batch)

    return {member[0] for member in guild_data_batch}

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

async def batch_assigned_guilds_update(update_set: set[str]):
    member_ids = await fetch_all_assigned_guild_member_ids()
    update_set.update(member_ids)
