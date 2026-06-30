import discord
from modal import GuildAssign, roleAssign
from database import get_discord_roles

EMOJI = '<:winemaking:1236751228231225364>'
BOT_NAME = "Infiniport.al"

class firstMessageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        self.gen_settings = discord.ui.Button(label="Server Settings", 
            style=discord.ButtonStyle.grey,
            custom_id="gen_settings")
        
        self.role_settings = discord.ui.Button(label="Role Settings", 
                            style=discord.ButtonStyle.grey,
                            custom_id="role_settings1")
        
        self.bot_commands = discord.ui.Button(label="Command List", 
                            style=discord.ButtonStyle.blurple,
                            custom_id="bot_commands")

        self.gen_settings.callback = self.gen_settings_callback
        self.role_settings.callback = self.role_settings_callback
        self.bot_commands.callback = self.bot_commands_callback

        self.add_item(self.gen_settings)
        self.add_item(self.role_settings)
        self.add_item(self.bot_commands)
    
    async def gen_settings_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=settings_embed(),
                                                view=settingsView(),
                                                ephemeral=True)

    async def role_settings_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=await roles_embed(interaction),
                                                view=rolesView(interaction.guild),
                                                ephemeral=True)

    async def bot_commands_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=commands_embed(), ephemeral=True)

class settingsView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=900.0)

        self.assign_guild = discord.ui.Button(label="Assign Guild", 
            style=discord.ButtonStyle.grey)
        self.assign_guild.callback = self.assign_guild_callback
        self.add_item(self.assign_guild)

    async def assign_guild_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(GuildAssign())

    async def on_timeout(self):
        try:
            self.stop()
        except Exception as e:
            print(f"Failed to stop View on timeout: {str(e)}")

class rolesView(discord.ui.View):
    def __init__(self, guild):
        super().__init__(timeout=900.0)
        self.chosen_role = None
        self.guild = guild

        roles = [role for role in guild.roles if not role.is_default()][:24]

        role_options = [
            discord.SelectOption(label=role.name, value=str(role.id))
            for role in roles
        ]
        
        options=[
            discord.SelectOption(label="Guild Admin", value="Guild_Admin"),
            discord.SelectOption(label="Guild Worker", value="Guild_Worker"),
            discord.SelectOption(label="Guild Member", value="Guild_Member"),
            discord.SelectOption(label="Shard Pledger", value="Shard_Pledger"),
            discord.SelectOption(label="Shard Owner", value="Shard_Owner"),
            #discord.SelectOption(label="Land_Pledger", value=),
            #discord.SelectOption(label="Land_Owner", value=),
            #discord.SelectOption(label="Player_Level", value=),
            #discord.SelectOption(label="Skill_Level", value=),
        ]
        if role_options:
            self.role_options = discord.ui.Select(
                placeholder="Select a role...",
                min_values=1,
                max_values=1,
                options=role_options
            )
            self.role_options.callback = self.role_options_callback
            self.add_item(self.role_options)
            
        self.select_object = discord.ui.Select(
            placeholder="Select a Pixels requirement for the role...",
            min_values=1,
            max_values=1,
            options=options
        )
        self.select_object.callback = self.select_object_callback
        self.add_item(self.select_object)

    async def role_options_callback(self, interaction: discord.Interaction):
        role_id = int(self.role_options.values[0])
        self.chosen_role = self.guild.get_role(role_id)
        await interaction.response.defer()

    async def select_object_callback(self, interaction: discord.Interaction):
        if self.chosen_role is not None:
            await interaction.response.send_modal(roleAssign(self.chosen_role, self.select_object.values[0]))
        else: 
            await interaction.response.defer()

    async def on_timeout(self):
        try:
            self.stop()
        except Exception as e:
            print(f"Failed to stop View on timeout: {str(e)}")


def join_embed():
  embed = discord.Embed(
      title=f"Welcome to the {BOT_NAME} Tool for Pixels.xyz",
      color=0x00ff00)
  embed.set_author(name=BOT_NAME)
  embed.add_field(name="",
            value="⚠️Keep this channel private to admins only!⚠️\n \n" +
            f"Anyone who can access this channel can modify the settings for your server's {BOT_NAME} application. \n \n" + 
            "To function as expected: \n"
            "- Collab.Land should also be within the Discord Server. \n" +
            "- The server must have an assigned Pixels Guild in [__Server Settings__]. \n" +
            "- The bot requires the `Administrator` role, or at a minimum the permissions: \n" +
            " > `Read Messages/View Channels`, \n" +
            " > `Send Messages`, \n" +
            " > `Manage Messages`, \n" +
            " > `Manage Channels`, \n" +
            " > `Manage Roles` \n" +
            " > `Embed Links` \n" +
            " > `Mention Everyone` \n" +
            " > `Use Activities` \n" +
            "- This `infiniportal-config` channel cannnot be deleted \n" +
            "- All settings changes and bot updates will occur in this channel"
            ,
            inline=False)
  embed.set_thumbnail(url='https://d31ss916pli4td.cloudfront.net/environments/icons/land.png')
  return embed

def settings_embed():
  embed = discord.Embed(
      title=f"{BOT_NAME} Settings:",
      color=0x00ff00)
  embed.add_field(name="",
            value=f"{EMOJI} Modify your server's {BOT_NAME} settings here! {EMOJI}\n \n" +
            "Assigning a Guild to your discord server affects the default `/leaderboard` displayed. \n" + 
            "It also allows for roles and commands to be restricted to approved Guild Members, Workers, or Admins automatically.\n \n" +
            "Assigning the `infiniportal-connect` message to the same channel as `collabland-connect` is recomended for an easier user expierience.\n\n"
            "Role settings can be modified for specific roles for Guild Admins, Workers, Members, Pledgers, and Supporters \n" +
            "Role settings can also provide specific roles for Player Skill Levels, VIP, and Landowner Status, including Pledged Lands (in progress)"
            ,
            inline=False)
  return embed

async def roles_embed(interaction: discord.Interaction):
    roles = None
    if interaction.guild is not None:
        roles = await get_discord_roles(str(interaction.guild.id))
    embed = discord.Embed(
                          title=f"{BOT_NAME} Role Settings:",
                          color=0x00ff00)
    embed.add_field(name="",
            value=f"{EMOJI} Modify your server's role settings here! {EMOJI}\n \n" +
            "- Roles can be given to users which connect their Pixels accounts in `infiniportal-connect`. \n \n" + 
            "- After choosing a role and access level, you will be able to input the number of (Staked) Shards required for the role.\n \n" +
            "- Roles are updated once a user links their account, and automatically hourly (soon).\n"
            "- Role settings can be modified for specific roles for Guild Admins, Workers, Members, Pledgers, Supporters and more!\n \n",
            inline=False)
    if roles and roles[6] and roles[7] and roles[8]:
        role_list = []
        role_ids_list = roles[6].split(' ')
        role_requirements_list = roles[7].split(' ')
        role_numbers_list = roles[8].split(' ')
        
        for i in range(len(role_ids_list)):
            role = None
            if interaction.guild is not None:
               role = interaction.guild.get_role(int(role_ids_list[i]))
            if role:
                formatted = '> ' + role.mention + ' - ' + role_requirements_list[i] + ': ' + role_numbers_list[i]
                role_list.append(formatted)

        if role_list:
            embed.add_field(name="Existing Roles:",
                value='\n'.join(role_list),
                inline=False)

    embed.add_field(name="", value="Create a new role rule below. \nCreating a new rule for a role with an existing rule will overwrite it:", inline=False)
    return embed

async def config_channel(channel):
    await channel.send(embed=join_embed(), view=firstMessageView())

def commands_embed():
  embed = discord.Embed(
      title=f"{BOT_NAME} Command List:",
      color=0x00ff00)
  embed.set_author(name=BOT_NAME)
  embed.add_field(name="",
            value=
            "- /lookup - `input:`\n  >  Lookup a Pixel player's profile using their username, userID, or wallet address.\n" +
            "- /leaderboard - `skill:` | `sort:` | `page_number:` \n  >  See the leaderboard of your server's assigned Guild. Only shard stakers with the Guild Member Role+ are shown\n" +
            "- /global_leaderboard - `skill:` | `sort:` | `page_number:` \n  >  See the global leaderboard of every Pixels Player.\n" +
            "- /task create \n  > Create a task for other players to complete! \n" +
            "- /taskboard \n  > View the tasks others have created"
            ,inline=False)
  embed.set_thumbnail(url='https://d31ss916pli4td.cloudfront.net/environments/icons/land.png')
  return embed