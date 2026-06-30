from constants import ICON, ICON_END, SKILLS
from database import get_pool
import discord


class LeaderboardView(discord.ui.View):
    def __init__(
        self,
        interaction,
        table_name: str = "total",
        arg: str = "level",
        page_number: int = 1,
        server_id=None,
    ):
        super().__init__(timeout=60.0)

        self.interaction = interaction
        self.table_name = table_name
        self.arg = arg
        self.page_number = page_number
        self.server_id = server_id

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.grey)
    async def previous_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        self.page_number = max(1, self.page_number - 1)
        await self.update_leaderboard(interaction)

    @discord.ui.button(label="Flip Order", style=discord.ButtonStyle.blurple)
    async def flip_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        self.arg = "exp" if self.arg == "level" else "level"
        await self.update_leaderboard(interaction)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.grey)
    async def next_button(
        self,
        interaction: discord.Interaction,
        _button: discord.ui.Button,
    ):
        self.page_number += 1
        await self.update_leaderboard(interaction)

    async def update_leaderboard(self, interaction: discord.Interaction):
        embed = await leaderboard_func(
            self.table_name,
            self.arg,
            self.page_number,
            self.server_id,
        )

        if embed is None:
            await interaction.response.edit_message(
                content=(
                    "Error, server leaderboard not set!\n"
                    "Make sure the server has an assigned guild in "
                    "`infiniportal-config`."
                ),
                embed=None,
                view=None,
            )
            return

        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        try:
            await self.interaction.edit_original_response(view=None)
        except Exception as e:
            print(f"Failed to edit message on timeout: {e}")


async def manage_leaderboard(
    interaction,
    table_name: str = "total",
    arg: str = "level",
    page_number: int = 1,
    server_id=None,
):
    page_number = max(1, page_number)

    try:
        embed = await leaderboard_func(table_name, arg, page_number, server_id)

        if embed:
            view = LeaderboardView(
                interaction,
                table_name,
                arg,
                page_number,
                server_id,
            )
            await interaction.response.send_message(
                embed=embed,
                view=view,
                ephemeral=False,
            )
        else:
            await interaction.response.send_message(
                "Error, try again!\n"
                "Make sure the server has an assigned guild in "
                "`infiniportal-config`.",
                ephemeral=True,
            )

    except Exception as e:
        print(f"/lb error: {e}")
        await interaction.response.send_message(
            "Error, server leaderboard not set!\n"
            "Make sure the server has an assigned guild in "
            "`infiniportal-config`.",
            ephemeral=True,
        )


async def leaderboard_func(
    table_name: str,
    order: str,
    page_number: int,
    server_id=None,
):
    valid_orders = ["level", "exp"]
    valid_tables = SKILLS.copy()
    valid_tables.append("total")

    if order not in valid_orders:
        order = "level"

    if table_name not in valid_tables:
        table_name = "total"

    page_number = max(1, int(page_number))
    limit = 10
    offset = limit * (page_number - 1)

    # Your old behavior:
    # - for total + level, order by level
    # - otherwise order by exp when level is selected
    order_column = "exp"
    if table_name == "total" and order == "level":
        order_column = "level"
    elif order == "exp":
        order_column = "exp"

    pool = await get_pool()

    guild_name = None
    guild_icon = None

    async with pool.acquire() as conn:
        if server_id:
            guild_row = await conn.fetchrow(
                """
                SELECT
                    ds.linked_guild,
                    g.handle,
                    g.emblem
                FROM discord_servers ds
                LEFT JOIN guilds g
                  ON g.id = ds.linked_guild
                WHERE ds.server_id = $1;
                """,
                str(server_id),
            )

            if guild_row is None or guild_row["linked_guild"] is None:
                return None

            guild_id = guild_row["linked_guild"]
            guild_name = guild_row["handle"]
            guild_icon = guild_row["emblem"]

            rows = await conn.fetch(
                f"""
                SELECT
                    u.username,
                    u.{order} AS display_value
                FROM {table_name} u
                JOIN guild_members gm
                  ON gm.user_id = u.user_id
                WHERE gm.guild_id = $1
                ORDER BY u.{order_column} DESC
                LIMIT $2 OFFSET $3;
                """,
                guild_id,
                limit,
                offset,
            )

        else:
            rows = await conn.fetch(
                f"""
                SELECT
                    username,
                    {order} AS display_value
                FROM {table_name}
                ORDER BY {order_column} DESC
                LIMIT $1 OFFSET $2;
                """,
                limit,
                offset,
            )

    title_prefix = ""
    if server_id and guild_name:
        title_prefix = f"{guild_name.title()} "

    embed = discord.Embed(
        title=f"{title_prefix}{table_name.title()} {order.title()} Leaderboard",
        description="",
        color=0x00FF00,
    )
    embed.set_footer(text=f"Page {page_number}")

    if guild_icon:
        if guild_icon.startswith("http"):
            embed.set_thumbnail(url=f"{guild_icon}?0.5060365238289637")
        else:
            embed.set_thumbnail(url=f"https:{guild_icon}?0.5060365238289637")

    if table_name != "total":
        embed.set_thumbnail(url=ICON + table_name.lower() + ICON_END)

    medals = ["🥇 ", "🥈 ", "🥉 "]

    for row_index, row in enumerate(rows):
        username = row["username"]
        value = row["display_value"]

        formatted_entry = f"{username} - {int(value):,}"

        if page_number == 1 and row_index < len(medals):
            formatted_entry = medals[row_index] + formatted_entry
        else:
            number = f"#{offset + row_index + 1} "
            formatted_entry = number + formatted_entry

        embed.add_field(name=formatted_entry, value="", inline=False)

    return embed