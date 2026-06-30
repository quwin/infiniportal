import discord
from discord.ext import tasks
from discord import app_commands
from profile_utils import lookup_profile, embed_profile
from database import init_db, delete_job
from leaderboard import manage_leaderboard
from constants import TOKEN, SkillEnum, SortEnum
from land import speck_data, nft_land_data, landowners_update
from modal import JobInput
from job import JobView, delete_job_message, readd_job_view
from collab_land import collab_channel, CollabButtons
from guild import all_guilds_data
import aiosqlite
import aiohttp
import time
from initalize_server import config_channel, firstMessageView
from taskboard import taskboard_embed

intents = discord.Intents.default()
client = discord.Client(intents=intents, command_prefix='!')
tree = app_commands.CommandTree(client)


@client.event
async def on_ready():
  try:
    await init_db()
    await tree.sync(guild=discord.Object(id=1234015429874417706))
    print(f'We have logged in as {client.application_id}')
  except Exception as e:
    print(f"Error: {e}")

  await init_job_views(client)
  await leave_personal_servers(client)
  client.add_view(CollabButtons())
  client.add_view(firstMessageView())
  batch_speck_update.start()
  batch_nft_land_update.start()
  # update_voice_channel_name.start()
  update_set_update.start()


@client.event
async def on_guild_join(guild: discord.Guild):
  # Doesn't work if they can be None
  if guild.default_role and guild.me:

    settings_overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        guild.me: discord.PermissionOverwrite(view_channel=True),
    }

    connect_overwrites = {
        guild.default_role:
        discord.PermissionOverwrite(send_messages=False),
        guild.me:
        discord.PermissionOverwrite(view_channel=True, send_messages=True),
    }
    settings = await guild.create_text_channel('infiniportal-config',
                                               overwrites=settings_overwrites)
    connect = await guild.create_text_channel('infiniportal-connect',
                                              overwrites=connect_overwrites)

    await config_channel(settings)
    await collab_channel(connect)


async def leave_personal_servers(client: discord.Client):
  for guild in client.guilds:
    member_count = guild.member_count
    if member_count is not None and member_count <= 3:
      config_channel = discord.utils.find(
          lambda c: c.name == 'infiniportal-config', guild.channels)
      connect_channel = discord.utils.find(
          lambda c: c.name == 'infiniportal-connect', guild.channels)

      if config_channel and config_channel.type == discord.ChannelType.text:
        try:
          await config_channel.delete()
        except Exception as e:
          print(
              f"Error deleting channel: {e} in guild {guild.name} (ID: {guild.id}) "
          )
      if connect_channel and connect_channel.type == discord.ChannelType.text:
        try:
          await connect_channel.delete()
        except Exception as e:
          print(
              f"Error deleting channel: {e} in guild {guild.name} (ID: {guild.id}) "
          )
      owner = guild.owner
      server_name = guild.name
      if owner is not None:
        try:
          await owner.send(embed=leave_server_embed(server_name))
          print(f'Sent message to the owner of guild: {guild.name}')
        except discord.Forbidden:
          general_channel = discord.utils.find(lambda c: c.name == 'general',
                                               guild.channels)
          if general_channel and general_channel.type == discord.ChannelType.text:
            try:
              await general_channel.send(embed=leave_server_embed(server_name))
              print(f'Sent message in #general of guild: {guild.name}')
            except discord.Forbidden:
              print(
                  f'Could not send message in #general of guild: {guild.name}')
      print(
          f'Leaving guild: {guild.name} (ID: {guild.id}) due to insufficient members ({member_count})'
      )
      await guild.leave()


def leave_server_embed(server_name):
  embed = discord.Embed(title=f"Important Infiniportal Announcement:",
                        color=0x00ff00)
  embed.add_field(
      name="",
      value="@everyone \n\n" +
      "Hi, this is the Infiniportal Dev Speaking. First, I would like to thank you for your support. "
      +
      "The Infiniportal Discord bot has reached 100 servers joined in only a day. However, this means that I have hit a limit of servers the bot can join. \n \n"
      +
      f"In order to free up space for other servers to use the bot, it has automatically left your server: {server_name} \n \n"
      +
      "I have determined that your use-case for the bot would be better served in a DM. You are free to interact with the Bot via DM.\n"
      "Feel free to use `/lookup` via direct message for your bot needs. \n" +
      "Alternatively, you and others which wish to use the bot may join the official Infiniportal Discord Server, which has all of it's functions available. \n"
      + "You may access it at: https://discord.gg/bNcywxF7u5\n" +
      "If you feel like your server needs the bot, or was removed unfairly, feel free to message @quwin, and I will get it sorted. \n"
      + "Thank You.",
      inline=False)
  embed.set_thumbnail(
      url='https://d31ss916pli4td.cloudfront.net/environments/icons/land.png')
  return embed


async def init_job_views(client: discord.Client):
  async with aiosqlite.connect('jobs.db') as db, db.execute(
      'SELECT job_id, time_limit, message_id, channel_id, server_id FROM jobs'
  ) as cursor:
    jobs = await cursor.fetchall()

  current_time: float = time.time()
  for row in jobs:
    expiration_date = float(row[1])
    job_id = row[0]
    message_id = row[2]
    channel_id = row[3]
    server_id = row[4]
    if current_time < expiration_date:
      if server_id is None:  # backwards compatability + DM compatability
        client.add_view(JobView(job_id, client))
      else:
        view_lifetime = expiration_date - current_time
        try:
          await readd_job_view(client, job_id, view_lifetime, message_id,
                               channel_id, server_id)
        except Exception as e:
          print(f'Job view add on init error: {e},\n{row}')
    else:
      try:
        await delete_job(job_id)
        await delete_job_message(job_id, client)
      except Exception as e:
        print(f'Job delete on init error: {e},\n{row}')


@tree.command(name="clear_commands",
              description="Clear commands",
              guild=discord.Object(id=1234015429874417706))
async def clear_commands(interaction, server: str | None = None):
  if interaction.user.id != 239235420104163328:
    return
  if server:
    tree.clear_commands(guild=discord.Object(id=server))
  else:
    tree.clear_commands(guild=None)
  if server is None:
    await tree.sync()
  else:
    await tree.sync(guild=discord.Object(id=server))
  await interaction.response.send_message('Command tree removed!',
                                          ephemeral=True)


@tree.command(name="add_commands",
              description="Add commands",
              guild=discord.Object(id=1234015429874417706))
async def add_commands(interaction, server: str | None = None):
  if interaction.user.id != 239235420104163328:
    return
  if server is None:
    await tree.sync()
  else:
    await tree.sync(guild=discord.Object(id=int(server)))
  await interaction.response.send_message('Command tree synced!',
                                          ephemeral=True)


@tree.command(name="raw_sql",
              description="break da database",
              guild=discord.Object(id=1234015429874417706))
async def raw_sql(interaction, database: str, execute: str):
  await interaction.response.defer()
  async with aiosqlite.connect(f'{database}.db') as db:
    await db.execute(execute)
    await db.commit()
  await interaction.followup.send(f'Executed command {execute}!')


@tree.command(name="lookup", description="Lookup a player's Pixels profile")
@app_commands.describe(
    input="Enter a user's Username, UserID, or Wallet Address")
async def lookup(interaction, input: str):
  try:
    async with aiosqlite.connect('leaderboard.db') as conn:
      result = await lookup_profile(conn, input)
      if result is None:
        string = f"Could not find the player `{input}`. Please try again"
        await interaction.response.send_message(string, ephemeral=True)
        return
      (data, total_levels, total_skills) = result

      embed = embed_profile(data, total_levels, total_skills)
      await interaction.response.send_message(embed=embed)

  except Exception as e:
    if interaction.guild:
      print(
          f"/lookup error in server {interaction.guild.id} / {interaction.guild.name}: {e}"
      )
    else:
      print(f"No guild in /lookup error! {e}")
    await interaction.followup.send(f"Error: {e}", ephemeral=True)


@tree.command(name="global_leaderboard",
              description="Look at a ranking of (almost) every Pixels Player!")
@app_commands.describe(skill="Select the skill to display",
                       sort="Select the sorting method",
                       page_number="Page number of the leaderboard")
async def global_leaderboard(interaction: discord.Interaction,
                             skill: SkillEnum = SkillEnum.NONE,
                             sort: SortEnum = SortEnum.LEVEL,
                             page_number: int = 1):
  skill_value = skill.value
  sort_value = sort.value
  try:
    await manage_leaderboard(interaction, skill_value, sort_value, page_number)
  except Exception as e:
    if interaction.guild:
      print(
          f"GLB Error in server {interaction.guild.id} / {interaction.guild.name}: {e}"
      )
    else:
      print(f"No guild in GLB error! {e}")
    await interaction.followup.send(f"Error: {e}", ephemeral=True)


@tree.command(name="leaderboard",
              description="Look at your server's Leaderboard!")
@app_commands.describe(skill="Select the skill to display",
                       sort="Select the sorting method",
                       page_number="Page number of the leaderboard")
async def leaderboard(interaction: discord.Interaction,
                      skill: SkillEnum = SkillEnum.NONE,
                      sort: SortEnum = SortEnum.LEVEL,
                      page_number: int = 1):
  skill_value = skill.value
  sort_value = sort.value
  if interaction.guild is None:
    await interaction.response.send_message(
        "This command can only be used in a server!", ephemeral=True)
    return
  server_id = interaction.guild.id
  try:
    await manage_leaderboard(interaction, skill_value, sort_value, page_number,
                             server_id)
  except Exception as e:
    print(
        f"Leadboard Error in server {server_id} / {interaction.guild.name}: {e}"
    )
    await interaction.followup.send(f"Error: {e}", ephemeral=True)


# Define the group
job_group = app_commands.Group(
    name="task",
    description="View, modify, and create tasks for other users to complete!")


# Create the subjobs
@job_group.command(name="create", description="Create a claimable task!")
async def create(interaction: discord.Interaction):
  view = JobView(interaction.id, client)
  await interaction.response.send_modal(JobInput(view))


tree.add_command(job_group)


# Main /taskboard
@tree.command(name="taskboard",
              description="View the tasks available to complete!")
@app_commands.describe(page_number="Enter the page to go to")
async def taskboard(interaction: discord.Interaction, page_number: int = 1):
  try:
    embed = await taskboard_embed(interaction, min(1, page_number))
    await interaction.response.send_message(embed=embed, ephemeral=True)
  except Exception as e:
    if interaction.guild:
      print(
          f"Taskboard error in server {interaction.guild.id} / {interaction.guild.name}: {e}"
      )
    else:
      print(f"No guild in Taskboard error! {e}")
    await interaction.response.send_message(f"Error: {e}", ephemeral=True)


@tasks.loop(minutes=2880)
async def batch_speck_update():
  async with aiosqlite.connect(
      'leaderboard.db') as conn, aiohttp.ClientSession() as session:
    await speck_data(conn, session)


update_set: set[str] = {
    '65e3dd3bebdfdac278077b85',
}  # My id cause why not


@tasks.loop(minutes=720)
async def update_set_update():
  await landowners_update(update_set)
  await all_guilds_data(update_set)

@tasks.loop(minutes=30)
async def batch_nft_land_update():  # Need to rename
  print(f'Updating {len(update_set)} Player(s)')
  async with aiosqlite.connect('leaderboard.db') as conn:
    await nft_land_data(conn, update_set)


client.run(TOKEN)
