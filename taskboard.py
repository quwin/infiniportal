import discord
from database import fetch_unclaimed_jobs

class TaskboardView(discord.ui.View):
    def __init__(self,
                 interaction,
                 page_number=1,
                 server_id=None):
        super().__init__(timeout=60.0)
    
        self.interaction = interaction
        self.page_number = page_number
        self.server_id = server_id
        
        self.label = 'Global Tasks'
        self.switch_tasks = discord.ui.Button(label=self.label, style=discord.ButtonStyle.blurple)
        self.switch_tasks.callback = self.switch_tasks_callback
        self.add_item(self.switch_tasks)
    
    @discord.ui.button(label='Previous', style=discord.ButtonStyle.grey)
    async def previous_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        self.page_number = max(1, self.page_number - 1)
        await self.update_taskboard(interaction)

    async def switch_tasks_callback(self, interaction: discord.Interaction):
        await self.update_taskboard(interaction)
        if self.label == 'Global Tasks':
            self.label = 'Server Tasks'
        else:
            self.label = 'Global Tasks'
        self.switch_tasks.label = self.label
    
    @discord.ui.button(label='Next', style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, _button: discord.ui.Button):
        self.page_number += 1
        await self.update_taskboard(interaction)
    
    async def update_taskboard(self, interaction: discord.Interaction):
        embed = await taskboard_embed(interaction, self.page_number)
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def on_timeout(self):
        try:
            await self.interaction.edit_original_response(view=None)
        except Exception as e:
            print(f"Failed to edit message on timeout: {str(e)}")

async def taskboard_embed(interaction: discord.Interaction, page_number: int):
    embed = discord.Embed(title='**Taskboard:**', color=0x00ff00)

    list = "----------------------------------------------------\n"
    
    unclaimed_jobs = await fetch_unclaimed_jobs(page_number, str(interaction.guild.id)) if interaction.guild else await fetch_unclaimed_jobs(page_number)
    for job in unclaimed_jobs:
        job_id, author_id, item, quantity, reward, details, time_limit, _, _, _, _  = job
        member = None
        if interaction.guild is not None:    
            member = interaction.guild.get_member(author_id)
        author = await interaction.client.fetch_user(author_id) if member is None else member
        list = list + f"**Requested by** <@{author.id}>\n\n"
        list = list + f"> **{quantity}** x {item} **---->** {reward}\n"
        if details != 'N/A':
            details = format_details_as_blockquote(details)
            list = list + f"> **Additional Info:** \n{details}\n"
        list = list + f"> Expiration Time: <t:{int(time_limit)}:R>\n"
        list = list + '----------------------------------------------------\n'
        embed.add_field(name='', value=list, inline=False)
        list = ""

    embed.add_field(name='', value="\n Create your own task using `/task create`", inline=False)

    return embed

# Helper function for /taskboard
def format_details_as_blockquote(details: str) -> str:
    lines = details.split('\n')
    formatted_lines = [f"> {line}" for line in lines]
    return '\n'.join(formatted_lines)