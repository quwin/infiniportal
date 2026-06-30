import discord
import time
from database import add_job
from guild import assignGuild
from roles import linkRole
from constants import RequirementType

pixelshine = '<a:PIXELshine:1241404259774496878>'
coin = '<:pixelcoin:1238636808951038092>'

class JobInput(discord.ui.Modal, title='Input Task Details:'):
    def __init__(self, view, job_data = None):
        super().__init__()
        self.view = view
        if job_data is not None:
            self.job_data = {
                'job_id': job_data[0],
                'author_id': job_data[1],
                'item': job_data[2],
                'quantity': job_data[3],
                'reward': job_data[4],
                'details': job_data[5],
                'time_limit': float(job_data[6]),
                'claimer_id': job_data[7],
                'message_id': job_data[8],
                'channel_id': job_data[9],
                'server_id': job_data[10]
            }
        else:
            self.job_data = {}
        self.add_item(discord.ui.TextInput(
            label='Item',
            placeholder='Popberry',
            default= self.job_data.get('item', None),
            max_length=36,
        ))

        self.add_item(discord.ui.TextInput(
            label='Quantity',
            placeholder='12',
            default= self.job_data.get('quantity', None),
            max_length=12,
        ))

        self.add_item(discord.ui.TextInput(
            label='Reward',
            placeholder='1000 Coins',
            default= self.job_data.get('reward', None),
            max_length=64,
        ))

        self.add_item(discord.ui.TextInput(
            label='What additional information do you have?',
            style=discord.TextStyle.long,
            required=False,
            default= self.job_data.get('details', 'N/A'),
            max_length=256,
        ))
        current_time: float = time.time()
        #24 hrs from current time
        expiration_date: float = self.job_data.get('time_limit', current_time + 86400.0)
        # Solve for hrs from current time
        time_delta: float = expiration_date - current_time
        input_hrs: str = str(max(round(time_delta/3600.0, 1), 0.02))
        self.add_item(discord.ui.TextInput(
            label='When should this job expire? (In Hours)',
            style=discord.TextStyle.long,
            required=False,
            default=input_hrs,
            max_length=5,
        ))
    
    async def on_submit(self, interaction: discord.Interaction):
        item = self.job_data.get("item", "")
        quantity = self.job_data.get("quantity", "0")
        reward = self.job_data.get("reward", "")
        details = self.job_data.get("details", "")
        time_limit = self.job_data.get("time_limit", 0.0)
        # conversions 
        try:
            expiration_date: float = (time_limit * 3600.0) + time.time()
        except ValueError:
            await interaction.response.send_message("Invalid input for time limit. Please enter a valid number.", ephemeral=True)
            return
        try:
            int_quantity: int = int(quantity)
        except ValueError:
            await interaction.response.send_message("Invalid input for quantity. Please enter a valid integer.", ephemeral=True)
            return
        
        if interaction.message:
            await interaction.message.delete()

        interaction_id = self.job_data.get("job_id", self.view.job_id)
        author_id = self.job_data.get("author_id", interaction.user.id)
        claimer_id = self.job_data.get("claimer_id", None)
            
         #Give View given timeout
        try:
            new_view = await self.view.recreate_with_new_timeout(self.view.job_id, float(time_limit)*3600.0, self.view.client)
            await self.view.delete_view()
        except Exception as e:
            new_view = self
            print(f" Recreate View error: {e}")
            await interaction.response.send_message("Error, could not complete the Task creation. Please Try Again.", ephemeral=True)
            return

        try:
            response = await create_or_edit_job(interaction, item, int_quantity, reward, details, expiration_date, new_view, interaction_id, claimer_id)
            message_id = self.job_data.get("message_id", response.id)
            channel_id = self.job_data.get("channel_id", response.channel.id)
    
            default_server = interaction.guild.id if interaction.guild else None
            server_id = self.job_data.get("server_id", default_server)

            await add_job(interaction_id, author_id, item, quantity, reward, details, expiration_date, message_id, channel_id, server_id, claimer_id)
        except Exception as e:
            print(f' Add_job error: {e}')
    
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        print(f" Job update/create error: {error}")
        await interaction.followup.send(f"Failed to create/update the job: {error}", ephemeral=True)
        return


async def create_or_edit_job(interaction: discord.Interaction, item, quantity, reward, details, time_limit, view, job_id=None,  claimer_id=None):
    embed = embed_job(interaction.user, item, quantity, reward, details, time_limit, claimer_id)
    await interaction.response.send_message(embed=embed, view=view)
    return await interaction.original_response()


def embed_job(author,
    item,
    quantity,
    reward,
    details,
    time_limit,
    claimer=None):
    
    embed = discord.Embed(
    title=
    f"{coin}\t**New Task Posted!**\t{coin}\n",
    color=0x00ff00)
    
    embed.set_author(name=f"Requested by {author.display_name}",
       icon_url=f"{author.display_avatar}")
    
    embed.add_field(name="",
      value=f"**{quantity}** x {item}\n\n" +
      "**Additional Info:\n**" + f"{details}\n\n" +
      "**Reward:**\n" + f"{reward}\n",
      inline=False)
    
    embed.add_field(name="Expiration Time:",
      value=f"<t:{int(time_limit)}:R>",
      inline=False)
    
    if claimer:
        embed.add_field(name="", value=f"Claimed by <@{claimer}> \n")
    return embed

class GuildAssign(discord.ui.Modal, title="Input Guild Handle:"):
    def __init__(self):
        super().__init__()
        self.guild_handle = discord.ui.TextInput(
            label="Guild Handle",
            placeholder="cookiemonsters",
            max_length=256,
            required=True,
        )
        self.add_item(self.guild_handle)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        guild_handle = str(self.guild_handle.value).strip()
        await assignGuild(interaction, guild_handle)

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
    ) -> None:
        print(f"Error: {error}")

        if interaction.response.is_done():
            await interaction.followup.send(
                f"Failed to assign a guild: {error}",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"Failed to assign a guild: {error}",
                ephemeral=True,
            )

class roleAssign(discord.ui.Modal, title='Input Role Information:'):
    def __init__(self, role: discord.Role, rule):
        super().__init__()
        self.role = role
        label, required = match_rule(rule)
        self.required = rule + '+' + required.value
        self.quantity = discord.ui.TextInput(
            label=f'{label}',
            placeholder='1',
            max_length=16,
            default='1',
        )
        self.add_item(self.quantity)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)
        await linkRole(interaction, self.role, self.required, str(self.quantity.value).strip())

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        print(f"Error: {error}")
        await interaction.followup.send(f"Failed to create the role: {str(self.role)}", ephemeral=True)
        return

def match_rule(rule):
    match str(rule):
        case "Guild_Admin":
            return ("Pledged Shards required", RequirementType.PLEDGE)
        case "Guild_Worker":
            return ("Pledged Shards required", RequirementType.PLEDGE)
        case "Guild_Member":
            return ("Pledged Shards required", RequirementType.PLEDGE)
        case "Shard_Pledger":
            return ("Pledged Shards required", RequirementType.PLEDGE)
        case "Shard_Supporter":
            return ("Shards owned", RequirementType.OWN)
        case "Land_Pledger":
            return ("Pledged Lands required", RequirementType.PLEDGE_LAND)
        case "Land_Owner":
            return ("Lands owned", RequirementType.OWN_LAND)
        case "Player_Level":    
            return ("Level Required", RequirementType.LEVEL)
        case "Skill_Level":
            return ("Level Required", RequirementType.LEVEL)
        case _:
            return ("Shards owned", RequirementType.OWN)