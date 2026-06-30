import discord
import time
from database import fetch_job, delete_job, update_job_claimer, update_job_message, fetch_job_location
from modal import JobInput, embed_job

pixelshine = '<a:PIXELshine:1241404259774496878>'
coin = '<:pixelcoin:1238636808951038092>'


class JobView(discord.ui.View):

    def __init__(self, job_id, client: discord.Client, timeout = None):
        super().__init__(timeout=timeout)
        self.client = client
        self.job_id = job_id
        self.last_bumped = time.time() - 300

        # Get job expiry data + expire it at that time

        # Each button needs to create in __init__() because of how the custom_id
        # is required to be in the same scope as job_id
        self.claim_button = discord.ui.Button(label="Claim",
                                              style=discord.ButtonStyle.green,
                                              custom_id=f"claim_{job_id}")
        self.unclaim_button = discord.ui.Button(label="Unclaim",
                                                style=discord.ButtonStyle.red,
                                                custom_id=f"unclaim_{job_id}")
        self.close_job_button = discord.ui.Button(
            label="Close",
            style=discord.ButtonStyle.blurple,
            custom_id=f"close_{job_id}")
        self.bump_button = discord.ui.Button(label="Bump Task",
                                             style=discord.ButtonStyle.gray,
                                             row=1,
                                             custom_id=f"bump_{job_id}")
        self.edit_button = discord.ui.Button(label="Edit Task",
                                             style=discord.ButtonStyle.gray,
                                             row=1,
                                             custom_id=f"edit_{job_id}")

        self.claim_button.callback = self.claim_button_callback
        self.unclaim_button.callback = self.unclaim_button_callback
        self.close_job_button.callback = self.close_job_button_callback
        self.bump_button.callback = self.bump_button_callback
        self.edit_button.callback = self.edit_button_callback

        self.add_item(self.claim_button)
        self.add_item(self.unclaim_button)
        self.add_item(self.close_job_button)
        self.add_item(self.bump_button)
        self.add_item(self.edit_button)

    async def claim_button_callback(self, interaction: discord.Interaction):
        await self.handle_interaction(interaction, "claim_")

    async def unclaim_button_callback(self, interaction: discord.Interaction):
        await self.handle_interaction(interaction, "unclaim_")

    async def close_job_button_callback(self,
                                        interaction: discord.Interaction):
        await self.handle_interaction(interaction, "close_job_")

    async def bump_button_callback(self, interaction: discord.Interaction):
        current_time = time.time()
        wait_time = current_time - self.last_bumped
        if wait_time < 300:
            await interaction.response.send_message(
                f"You can bump this task again <t:{int(current_time+300-wait_time)}:R>",
                ephemeral=True)
            return
        self.last_bumped = current_time
        await self.bump_message(interaction)

    async def edit_button_callback(self, interaction: discord.Interaction):
        try:
            current_time = time.time()
            wait_time = current_time - self.last_bumped
            if wait_time < 300:
                await interaction.response.send_message(
                    f"You can edit this task again <t:{int(current_time+300-wait_time)}:R>",
                    ephemeral=True)
                return

            job_data = await fetch_job(self.job_id)
            if job_data and job_data[1] == interaction.user.id:
                await interaction.response.send_modal(JobInput(self, job_data))
            else:
                await interaction.response.defer()
                return
        except Exception as e:
            await job_error(e, interaction)

    async def handle_interaction(self, interaction: discord.Interaction,
                                 custom_id: str):
        try:
            await interact_job(interaction, self, self.job_id, custom_id)
        except Exception as e:
            await job_error(e, interaction)

    async def bump_message(self, interaction: discord.Interaction):
        try:
            original_message = interaction.message
            if original_message:
                embed = original_message.embeds[
                    0] if original_message.embeds else None
                await original_message.delete()
                if embed:
                    await interaction.response.send_message(embed=embed, view=self)
                    
                    sent_message = await interaction.original_response()
                    message_id = sent_message.id
                    await update_job_message(self.job_id, message_id)

        
        except Exception as e:
            await job_error(e, interaction)

    async def on_timeout(self):
        await delete_job_message(self.job_id, self.client)
        await delete_job(self.job_id)

    @classmethod
    async def recreate_with_new_timeout(cls, job_id, timeout, client):
        new_view = JobView(job_id, client, timeout)
        return new_view

    async def delete_view(self):
        # Stop the view to ensure it's no longer active
        self.stop()


async def job_error(error, interaction: discord.Interaction | None):
    if interaction:
        await interaction.followup.send(
            f"An error occurred while processing your request: {error} \nMake sure that Infiniportal has the required permissions for viewing and interacting with this channel!",
            ephemeral=True)


async def interact_job(interaction: discord.Interaction, view, job_id: str, button: str):
    job = await fetch_job(job_id)
    if job:
        job_id, author_id, item, quantity, reward, details, time_limit, claimer_id, message_id, channel_id, server_id = job

        # Avoids API Call to recieve author if not necessary
        member = None
        if interaction.guild is not None:
            member = interaction.guild.get_member(author_id)
        author = await interaction.client.fetch_user(
            author_id) if member is None else member

        # Update the embed and job status based on the custom_id
        if button == "claim_":
            if not claimer_id:
                claimer_id = interaction.user.id
                await update_job_claimer(job_id, claimer_id)
            await interaction.response.defer()

        elif button == "unclaim_":
            if claimer_id == interaction.user.id or author.id == interaction.user.id:
                claimer_id = None
                await update_job_claimer(job_id, claimer_id)
            await interaction.response.defer()

        elif button == "close_job_":
            if interaction.user.id == author_id:
                if claimer_id is not None:
                    await interaction.response.send_message(
                        f"{interaction.user.mention}'s task of {quantity} x {item} has been completed by <@{claimer_id}> for {reward}!"
                    )

                await delete_job(job_id)
                if interaction.message is not None:
                    await interaction.message.delete()
                return
            elif interaction.user.id == claimer_id:
                await interaction.response.send_message(
                    f"<@{author_id}>'s task of {quantity} x {item} has been completed by {interaction.user.mention} for {reward}!"
                )
                await delete_job(job_id)
                if interaction.message is not None:
                    await interaction.message.delete()
                return
            else:
                await interaction.response.defer()

        embed = embed_job(author, item, quantity, reward, details, time_limit, claimer_id)
        if interaction.message is not None:
            await interaction.message.edit(embed=embed, view=view)

async def delete_job_message(job_id, client):
    try:
        job_data = await fetch_job_location(job_id)
        if job_data:
            message_id = job_data[0]
            channel_id = job_data[1]
            server_id = job_data[2]
            guild = client.get_guild(int(server_id))
            if guild:
                channel = guild.get_channel(int(channel_id))
                if channel and channel.type == discord.ChannelType.text:
                    message: discord.Message = await channel.fetch_message(int(message_id))
                    if message:
                        await message.delete()
                        print(f"Auto deleted task {job_id}")
                
    
    except Exception as e:
        print(e)
        await job_error(e, None)

async def readd_job_view(client: discord.Client, job_id, view_lifetime: float, message_id: str, channel_id: str, server_id: str):
    guild = client.get_guild(int(server_id))
    if guild:
        required_permissions = discord.Permissions(
            view_channel=True,
            read_messages=True,
            send_messages=True,
            manage_messages=True,
            embed_links=True
        )
        me = guild.me
        if not me.guild_permissions.is_superset(required_permissions):
            print("Bot does not have the required permissions in the guild.")
        channel = guild.get_channel(int(channel_id))
        if channel and channel.type == discord.ChannelType.text:
            message: discord.Message = await channel.fetch_message(int(message_id))
            if message.embeds:
                await message.edit(embed=message.embeds[0], view=JobView(job_id, client, view_lifetime))
                print(f'Message {message_id} in channel {channel_id} in server {server_id} reloaded')