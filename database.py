from constants import DATABASE_URL, SKILLS
import os
import ssl
import tempfile
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import asyncpg

from constants import SKILLS

DATABASE_URL = os.environ["DATABASE_URL"]

_pool: asyncpg.Pool | None = None


def _ssl_context_from_aiven_ca() -> ssl.SSLContext:
    ca_path = os.environ.get("AIVEN_CA_PATH")
    ca_contents = os.environ.get("AIVEN_CA")

    if ca_path:
        if not os.path.exists(ca_path):
            raise RuntimeError(
                f"AIVEN_CA_PATH is set to {ca_path}, but that file does not exist."
            )

        return ssl.create_default_context(cafile=ca_path)

    if ca_contents:
        cert_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".pem",
            delete=False,
        )
        cert_file.write(ca_contents)
        cert_file.flush()
        cert_file.close()

        return ssl.create_default_context(cafile=cert_file.name)

    raise RuntimeError(
        "DATABASE_URL uses sslmode=verify-ca or verify-full, but neither "
        "AIVEN_CA_PATH nor AIVEN_CA is set."
    )


def normalize_asyncpg_dsn(dsn: str) -> tuple[str, ssl.SSLContext | bool | None]:
    parsed = urlparse(dsn)
    query_params = dict(parse_qsl(parsed.query))

    sslmode = query_params.pop("sslmode", None)

    cleaned_query = urlencode(query_params)
    cleaned_dsn = urlunparse(parsed._replace(query=cleaned_query))

    if sslmode in {"verify-ca", "verify-full", "require"}:
        ssl_context = _ssl_context_from_aiven_ca()

        if sslmode == "verify-ca":
            ssl_context.check_hostname = False

        return cleaned_dsn, ssl_context

    return cleaned_dsn, None


async def get_pool() -> asyncpg.Pool:
    global _pool

    if _pool is None:
        dsn, ssl_config = normalize_asyncpg_dsn(DATABASE_URL)

        _pool = await asyncpg.create_pool(
            dsn=dsn,
            ssl=ssl_config,
            min_size=1,
            max_size=5,
        )

    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def init_db():
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS total (
                user_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                level INTEGER NOT NULL,
                exp DOUBLE PRECISION NOT NULL
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS guilds (
                id TEXT PRIMARY KEY,
                handle TEXT NOT NULL,
                emblem TEXT,
                shard_price INTEGER,
                land_count INTEGER
            );
            """
        )

        for skill in SKILLS:
            await conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {skill} (
                    user_id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    level INTEGER NOT NULL,
                    exp DOUBLE PRECISION NOT NULL,
                    current_exp DOUBLE PRECISION NOT NULL
                );
                """
            )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_members (
                guild_id TEXT NOT NULL REFERENCES guilds(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL,
                username TEXT NOT NULL,
                role TEXT NOT NULL,
                PRIMARY KEY (guild_id, user_id)
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                author_id BIGINT,
                item TEXT,
                quantity INTEGER,
                reward TEXT,
                details TEXT,
                time_limit DOUBLE PRECISION,
                claimer_id BIGINT,
                message_id BIGINT,
                channel_id BIGINT,
                server_id BIGINT
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS discord_servers (
                server_id TEXT PRIMARY KEY,
                premium DOUBLE PRECISION,
                linked_guild TEXT,
                global_tasks BOOLEAN,
                account_linking BOOLEAN,
                admin_role TEXT,
                role_ids TEXT,
                role_requirements TEXT,
                role_numbers TEXT
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS discord_users (
                user_id TEXT PRIMARY KEY,
                wallets TEXT,
                pixels_ids TEXT,
                primary_id TEXT,
                access_token TEXT,
                refresh_token TEXT
            );
            """
        )

    print("Postgres database initialized!")


async def update_skills(conn, data, total_level, total_exp):
    if data is None:
        return

    await conn.execute(
        """
        INSERT INTO total (user_id, username, level, exp)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id)
        DO UPDATE SET
            username = EXCLUDED.username,
            level = EXCLUDED.level,
            exp = EXCLUDED.exp;
        """,
        data["_id"],
        data["username"],
        total_level,
        total_exp,
    )

    for skill in SKILLS:
        skill_data = data["levels"].get(skill)
        if skill_data:
            await conn.execute(
                f"""
                INSERT INTO {skill} (user_id, username, level, exp, current_exp)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    username = EXCLUDED.username,
                    level = EXCLUDED.level,
                    exp = EXCLUDED.exp,
                    current_exp = EXCLUDED.current_exp;
                """,
                data["_id"],
                data["username"],
                skill_data["level"],
                skill_data["totalExp"],
                skill_data["exp"],
            )


async def init_guild_db(guild_data, server_id=None):
    if guild_data is None:
        return

    pool = await get_pool()

    guild_id = guild_data["_id"]

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO guilds (id, handle, emblem, shard_price, land_count)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (id)
                DO UPDATE SET
                    handle = EXCLUDED.handle,
                    emblem = EXCLUDED.emblem,
                    shard_price = EXCLUDED.shard_price,
                    land_count = EXCLUDED.land_count;
                """,
                guild_id,
                guild_data["handle"],
                guild_data.get("emblem", ""),
                guild_data["membershipsCount"],
                guild_data["mapCount"],
            )

            if server_id:
                await conn.execute(
                    """
                    INSERT INTO discord_servers (server_id, linked_guild)
                    VALUES ($1, $2)
                    ON CONFLICT (server_id)
                    DO UPDATE SET linked_guild = EXCLUDED.linked_guild;
                    """,
                    str(server_id),
                    guild_id,
                )


async def replace_guild_members(guild_id: str, members: list[tuple[str, str, str]]):
    pool = await get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM guild_members WHERE guild_id = $1;",
                guild_id,
            )

            if members:
                await conn.executemany(
                    """
                    INSERT INTO guild_members (guild_id, user_id, username, role)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (guild_id, user_id)
                    DO UPDATE SET
                        username = EXCLUDED.username,
                        role = EXCLUDED.role;
                    """,
                    [(guild_id, user_id, username, role) for user_id, username, role in members],
                )


async def update_job_claimer(job_id, claimer_id):
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE jobs
            SET claimer_id = $1
            WHERE job_id = $2;
            """,
            claimer_id,
            job_id,
        )


async def update_job_message(job_id, message_id):
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE jobs
            SET message_id = $1
            WHERE job_id = $2;
            """,
            message_id,
            job_id,
        )


async def delete_job(job_id):
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            DELETE FROM jobs
            WHERE job_id = $1;
            """,
            job_id,
        )


async def fetch_job(job_id):
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM jobs
            WHERE job_id = $1;
            """,
            job_id,
        )

    return tuple(row) if row else None


async def fetch_job_location(job_id):
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT message_id, channel_id, server_id
            FROM jobs
            WHERE job_id = $1;
            """,
            job_id,
        )

    return tuple(row) if row else None


async def add_job(
    job_id,
    author_id,
    item,
    quantity,
    reward,
    details,
    time_limit,
    message_id,
    channel_id,
    server_id,
    claimer_id=None,
):
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO jobs (
                job_id,
                author_id,
                item,
                quantity,
                reward,
                details,
                time_limit,
                claimer_id,
                message_id,
                channel_id,
                server_id
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (job_id)
            DO UPDATE SET
                author_id = EXCLUDED.author_id,
                item = EXCLUDED.item,
                quantity = EXCLUDED.quantity,
                reward = EXCLUDED.reward,
                details = EXCLUDED.details,
                time_limit = EXCLUDED.time_limit,
                claimer_id = EXCLUDED.claimer_id,
                message_id = EXCLUDED.message_id,
                channel_id = EXCLUDED.channel_id,
                server_id = EXCLUDED.server_id;
            """,
            str(job_id),
            author_id,
            item,
            int(quantity),
            reward,
            details,
            float(time_limit),
            claimer_id,
            message_id,
            channel_id,
            server_id,
        )


async def fetch_unclaimed_jobs(page_number: int = 1, server: str | None = None):
    pool = await get_pool()

    limit = 4
    offset = limit * (page_number - 1)

    async with pool.acquire() as conn:
        if server:
            rows = await conn.fetch(
                """
                SELECT *
                FROM jobs
                WHERE claimer_id IS NULL
                  AND server_id = $1
                ORDER BY time_limit ASC
                LIMIT $2 OFFSET $3;
                """,
                int(server),
                limit,
                offset,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT *
                FROM jobs
                WHERE claimer_id IS NULL
                ORDER BY time_limit ASC
                LIMIT $1 OFFSET $2;
                """,
                limit,
                offset,
            )

    return [tuple(row) for row in rows]


async def fetch_linked_wallets(user_id):
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM discord_users
            WHERE user_id = $1;
            """,
            str(user_id),
        )

    return tuple(row) if row else None


async def add_collab_tokens(user_id, access_token, refresh_token):
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO discord_users (user_id, access_token, refresh_token)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id)
            DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token;
            """,
            str(user_id),
            access_token,
            refresh_token,
        )


async def add_collab_wallets(user_id, wallets, pixels_ids):
    pool = await get_pool()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO discord_users (user_id, wallets, pixels_ids)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id)
            DO UPDATE SET
                wallets = EXCLUDED.wallets,
                pixels_ids = EXCLUDED.pixels_ids;
            """,
            str(user_id),
            wallets,
            pixels_ids,
        )

    print(f"Inserted {wallets} linked to {pixels_ids} into database for {user_id}!")


async def batch_update_players(conn, total_data_batch, skill_data_batch):
    if total_data_batch:
        await conn.executemany(
            """
            INSERT INTO total (user_id, username, level, exp)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (user_id)
            DO UPDATE SET
                username = EXCLUDED.username,
                level = EXCLUDED.level,
                exp = EXCLUDED.exp;
            """,
            total_data_batch,
        )
        total_data_batch.clear()

    skill_data_batch.pop("total", None)

    for skill, batch in skill_data_batch.items():
        if not batch:
            continue

        await conn.executemany(
            f"""
            INSERT INTO {skill} (user_id, username, level, exp, current_exp)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id)
            DO UPDATE SET
                username = EXCLUDED.username,
                level = EXCLUDED.level,
                exp = EXCLUDED.exp,
                current_exp = EXCLUDED.current_exp;
            """,
            batch,
        )
        batch.clear()


async def get_discord_roles(server_id):
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM discord_servers
            WHERE server_id = $1;
            """,
            str(server_id),
        )

    return tuple(row) if row else None


async def get_guild_handle(guild_id):
    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT handle
            FROM guilds
            WHERE id = $1;
            """,
            guild_id,
        )

    return tuple(row) if row else None

async def fetch_all_jobs():
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                job_id,
                time_limit,
                message_id,
                channel_id,
                server_id
            FROM jobs;
            """
        )

    return [dict(row) for row in rows]

async def fetch_all_assigned_guild_member_ids() -> set[str]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT user_id
            FROM guild_members;
            """
        )
    return {row["user_id"] for row in rows}