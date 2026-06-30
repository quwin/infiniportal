import discord
import aiohttp

from database import get_pool, get_discord_roles, get_guild_handle
from guild import guild_data


async def linkRole(
    interaction: discord.Interaction,
    role: discord.Role,
    requirement: str,
    quantity: str,
):
    if not interaction.guild:
        return

    server_id = str(interaction.guild.id)
    role_id = str(role.id)

    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT role_ids, role_requirements, role_numbers
            FROM discord_servers
            WHERE server_id = $1;
            """,
            server_id,
        )

        if row:
            role_ids = row["role_ids"]
            role_requirements = row["role_requirements"]
            role_numbers = row["role_numbers"]

            role_ids_list = role_ids.split(" ") if role_ids else []
            role_requirements_list = (
                role_requirements.split(" ") if role_requirements else []
            )
            role_numbers_list = role_numbers.split(" ") if role_numbers else []

            if role_id in role_ids_list:
                index = role_ids_list.index(role_id)
                role_requirements_list[index] = requirement
                role_numbers_list[index] = quantity
            else:
                role_ids_list.append(role_id)
                role_requirements_list.append(requirement)
                role_numbers_list.append(quantity)

            updated_role_ids = " ".join(role_ids_list)
            updated_role_requirements = " ".join(role_requirements_list)
            updated_role_numbers = " ".join(role_numbers_list)

        else:
            updated_role_ids = role_id
            updated_role_requirements = requirement
            updated_role_numbers = quantity

        await conn.execute(
            """
            INSERT INTO discord_servers (
                server_id,
                role_ids,
                role_requirements,
                role_numbers
            )
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (server_id)
            DO UPDATE SET
                role_ids = EXCLUDED.role_ids,
                role_requirements = EXCLUDED.role_requirements,
                role_numbers = EXCLUDED.role_numbers;
            """,
            server_id,
            updated_role_ids,
            updated_role_requirements,
            updated_role_numbers,
        )

    await interaction.followup.send(
        f"Successfully created or updated requirements for the role: {role.mention}",
        ephemeral=True,
    )


async def check_eligibility(
    interaction: discord.Interaction,
    primary_id: str,
) -> list[str]:
    if interaction.guild is None:
        return []

    server_id = str(interaction.guild.id)
    role_data = await get_discord_roles(server_id)

    valid_roles: list[str] = []

    if not role_data:
        print(f"No role data found for server {server_id}")
        return valid_roles

    linked_guild = role_data[2]
    role_ids_raw = role_data[6]
    role_requirements_raw = role_data[7]
    role_numbers_raw = role_data[8]

    if not linked_guild or not role_ids_raw or not role_requirements_raw or not role_numbers_raw:
        print(f"Invalid role data {role_data} for server {server_id}")
        return valid_roles

    guild_handle = await get_guild_handle(linked_guild)

    guild_info = None

    async with aiohttp.ClientSession() as session:
        if guild_handle is not None:
            guild_info = await guild_data(session, guild_handle[0])

    if guild_info is None:
        print(f"Could not fetch guild info for linked guild {linked_guild}")
        return valid_roles

    guild_members = guild_info.get("guildMembers")

    if guild_members is None:
        print(f"No guild members found for linked guild {linked_guild}")
        return valid_roles

    role_ids = role_ids_raw.split(" ")
    role_requirements = role_requirements_raw.split(" ")
    role_numbers = role_numbers_raw.split(" ")

    rule_count = min(len(role_ids), len(role_requirements), len(role_numbers))

    for i in range(rule_count):
        role_id = role_ids[i]
        requirement_format = role_requirements[i].split("+")
        quantity = role_numbers[i]

        is_valid = check_guild_conditions(
            guild_members,
            primary_id,
            requirement_format,
            quantity,
        )

        if is_valid:
            valid_roles.append(role_id)

    return valid_roles


def check_guild_conditions(
    data,
    player_id: str,
    role_requirements: list[str],
    quantity: str,
) -> bool:
    if len(role_requirements) < 2:
        return False

    requirement = role_requirements[0].split("_")

    if len(requirement) < 2:
        return False

    required_guild_role = requirement[1]
    quantity_field = role_requirements[1]

    try:
        required_quantity = float(quantity)
    except ValueError:
        return False

    for item in data:
        player = item.get("player", {})
        player_role = item.get("role")

        if player.get("_id") != player_id:
            continue

        if player_role != required_guild_role:
            continue

        try:
            actual_quantity = float(item.get(quantity_field, "-inf"))
        except ValueError:
            actual_quantity = float("-inf")

        if actual_quantity >= required_quantity:
            print(
                f"Found role for player {player_id} | "
                f"{player_role} | {required_quantity}\n"
            )
            return True

    return False