import discord
from database import fetch_linked_wallets
from constants import COLLAB_ID, REDIRECT_URI
from rate_limiter import AdaptiveRateLimiter
from profile_utils import get_accounts_usernames
from roles import check_eligibility

userlimiter = AdaptiveRateLimiter(3, 1)
users_checking = []

class CollabButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.start_button = discord.ui.Button(label="Let's Go!", 
                                              style=discord.ButtonStyle.blurple,
                                              custom_id="link_collab_start")
        self.why_button = discord.ui.Button(label="Why Collab.Land?",
                                            style=discord.ButtonStyle.grey,
                                            custom_id="why_collab_land")
        self.docs_button = discord.ui.Button(label="Collab.Land Docs",
                                                  style=discord.ButtonStyle.grey,
                                                  url="https://docs.collab.land/")

        self.start_button.callback = self.start_button_callback
        self.why_button.callback = self.why_button_callback

        self.add_item(self.start_button)
        self.add_item(self.why_button)
        self.add_item(self.docs_button)

    async def start_button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await manage_collab_link(interaction)
    
    async def why_button_callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "Collab.Land is a robust, easy to connect, and easy to integrate service which allows servers to link Discord accounts to Crypto Wallets. \n \n" +
            "This application uses your crypto wallets you have linked to your Pixels account in order to verify that you have ownership of the given Pixels account.\n \n" +
            "Collab.Land is used by many Pixels Guilds discords to verify shard ownership, and is even used by the Official Pixels discord itself. \n \n" + 
            "When linking your crypto wallet with Collab.Land and Cookie Monster, I will not have access to any personal or sensitive data. I will not ask for users to send any transactions, or ask for a seed phrase. \n \n Thanks.",
            ephemeral=True)


async def manage_collab_link(interaction):
    user_id = str(interaction.user.id)
    existing_wallets = await fetch_linked_wallets(user_id)
    
    if existing_wallets and existing_wallets[2]:
        pixels_ids = list(set(existing_wallets[2].split(" ")))
        username_json = await get_accounts_usernames(userlimiter, pixels_ids)
        usernames = [username_json.get(id) for id in pixels_ids]
    else:
        pixels_ids = []
        usernames = []
        
    embed = await show_linked_accounts(usernames)
    await interaction.followup.send(embed=embed, view=linkedAccountsView(user_id, pixels_ids, usernames), ephemeral=True)

# Embed for showing how to link your Pixels Account to the Bot
def collab_embed():
    embed = discord.Embed(
          title="Link your Pixels.xyz account",
          color=0x00ff00)
    embed.set_author(name="Infiniportal")
    embed.add_field(name="",
                  value="This is a read-only connection. Do not share your private keys. " +
                  "We will never ask for your seed phrase. We will never DM you.\n" + 
                  "This verification process is done through <@704521096837464076>",
                  inline=False)
    embed.set_thumbnail(url='https://d31ss916pli4td.cloudfront.net/environments/icons/land.png')
    return embed

# Create and manage collab_embed()
async def collab_channel(channel):
    await channel.send(embed=collab_embed(), view=CollabButtons())

        
# Function to show the linked accounts, and allow people to link their accounts
async def show_linked_accounts(usernames):
    if usernames:
        embed = discord.Embed(
              title="My Connected Pixels.xyz Accounts",
              description="Data powered by Collab.Land\n \n",
              color=0x00ff00)
        accounts = ''
        for name in usernames:
            accounts += f"- {name} \n"

        embed.add_field(name="", value=accounts, inline=False)
    else:
        embed = discord.Embed(
              title="My Connected Pixels.xyz Accounts",
              description="Data powered by <@704521096837464076>\n",
              color=0x00ff00)
        accounts = 'You have no accounts linked! Please link one by clicking the button below.'
        embed.add_field(name="", value=accounts, inline=False)

    return embed

class linkedAccountsView(discord.ui.View):
    def __init__(self, user_id, pixels_ids, usernames):
        super().__init__(timeout=900.0)
        self.user_id = user_id
        self.pixels_ids = pixels_ids
        self.usernames = usernames
        if pixels_ids:
            self.primary_id = pixels_ids[0]
        else:
            self.primary_id = None
        #users_checking.append(user_id)
        auth_url = (
            f"https://api.collab.land/oauth2/authorize"
            "?response_type=code"
            f"&client_id={COLLAB_ID}"
            f"&redirect_uri={REDIRECT_URI}"
            f"&scope=user:wallet:read"
            f"&state={user_id}"
        )

        if self.usernames:
            options=[]
            for username in self.usernames:
                options.append(discord.SelectOption(label=f"{username}"))
                
            self.select_menu = discord.ui.Select(
                placeholder="Select your primary Pixels account:",
                min_values=1,
                max_values=1,
                options=options,
            )
        
            self.select_menu.callback = self.select_callback
            self.add_item(self.select_menu)
        
        self.get_roles = discord.ui.Button(label="Check Roles", 
            style=discord.ButtonStyle.blurple)

        self.add_acc = discord.ui.Button(label="Add a new Account", 
            style=discord.ButtonStyle.blurple,
            url = auth_url)
        
        self.get_roles.callback = self.get_roles_callback
        self.add_item(self.get_roles)
        self.add_item(self.add_acc)


    async def get_roles_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        if self.primary_id and interaction.guild:
            valid_roles = await check_eligibility(interaction, self.primary_id)
            user = interaction.guild.get_member(interaction.user.id)
            if user is None:
                user = await interaction.guild.fetch_member(interaction.user.id)
            for role_id in valid_roles:
                role = interaction.guild.get_role(int(role_id))
                if role:
                    try:
                        await user.add_roles(role)
                        await interaction.followup.send(f"Role {role.mention} added to user '{user.display_name}'.", ephemeral=True)
                        return
                    except discord.Forbidden:
                        await interaction.followup.send("Role setting failed, improper permissions granted", ephemeral=True)
                        return
                    except discord.HTTPException as e:
                        await interaction.followup.send(f"Failed to add role: {e}", ephemeral=True)
                        return
                else:
                    await interaction.followup.send("No Roles to assign!", ephemeral=True)
                    return
            await interaction.followup.send("No Roles to assign!", ephemeral=True)
            return
        else:
            await interaction.followup.send("Please link a Pixels Account and select a primary account! \n If you already have, close both tabs and try again!", ephemeral=True)

    async def select_callback(self, interaction: discord.Interaction):
        selected_value = self.select_menu.values[0]
        self.primary_id = self.pixels_ids[self.usernames.index(selected_value)]
        await interaction.response.defer()

    async def on_timeout(self):
        try:
            if self.user_id in users_checking:
                users_checking.remove(self.user_id)
            self.stop()
        except Exception as e:
            print(f"Failed to stop View on timeout: {str(e)}")