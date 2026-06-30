from quart import (
    Quart,
    jsonify,
    redirect,
    render_template_string,
    request,
    send_from_directory,
    url_for,
)
from constants import (
    COLLAB_ID,
    COLLAB_KEY,
    COLLAB_SECRET,
    PROFILE_MID_LINK,
    REDIRECT_URI,
    SEARCH_PROFILE_LINK,
    SERVER_IP,
    SKILLS,
)
from database import (
    add_collab_tokens,
    add_collab_wallets,
    close_pool,
    get_pool,
    init_db,
)
from profile_utils import profile_finder

import aiohttp
import os
import urllib.parse

app = Quart(__name__, static_folder="frontend/build", static_url_path="")


@app.before_serving
async def startup():
    await init_db()


@app.after_serving
async def shutdown():
    await close_pool()


@app.route("/health", methods=["GET"])
async def health():
    return jsonify({"status": "ok"})


@app.route(
    "/leaderboard/<table_name>/<order>/<page_number>/<quantity>",
    defaults={"guild_name": None},
    methods=["GET"],
)
@app.route(
    "/leaderboard/<table_name>/<order>/<page_number>/<quantity>/<guild_name>",
    methods=["GET"],
)
async def get_leaderboard(
    table_name: str,
    order: str,
    page_number: str,
    quantity: str,
    guild_name: str | None = None,
):
    valid_orders = ["level", "exp"]
    valid_tables = SKILLS.copy()
    valid_tables.append("total")

    try:
        page_number_int = int(page_number)
        quantity_int = int(quantity)
    except ValueError:
        return jsonify({"error": "Invalid quantity or page number"}), 400

    if page_number_int < 1 or quantity_int < 1:
        return jsonify({"error": "Quantity and page number must be positive"}), 400

    if order not in valid_orders or table_name not in valid_tables:
        return jsonify({"error": "Invalid table name or order"}), 400

    offset = quantity_int * (page_number_int - 1)

    # Keep your old leaderboard behavior:
    # - total + level sorts by level
    # - otherwise level view sorts by exp
    order_column = "exp"
    if table_name == "total" and order == "level":
        order_column = "level"
    elif order == "exp":
        order_column = "exp"

    try:
        pool = await get_pool()

        async with pool.acquire() as conn:
            if guild_name:
                guild_row = await conn.fetchrow(
                    """
                    SELECT id
                    FROM guilds
                    WHERE handle = $1;
                    """,
                    guild_name,
                )

                if guild_row:
                    rows = await conn.fetch(
                        f"""
                        SELECT
                            u.username,
                            u.user_id,
                            u.level,
                            u.exp
                        FROM {table_name} u
                        JOIN guild_members gm
                          ON gm.user_id = u.user_id
                        WHERE gm.guild_id = $1
                        ORDER BY u.{order_column} DESC
                        LIMIT $2 OFFSET $3;
                        """,
                        guild_row["id"],
                        quantity_int,
                        offset,
                    )
                else:
                    rows = await conn.fetch(
                        f"""
                        SELECT
                            username,
                            user_id,
                            level,
                            exp
                        FROM {table_name}
                        ORDER BY {order_column} DESC
                        LIMIT $1 OFFSET $2;
                        """,
                        quantity_int,
                        offset,
                    )

            else:
                rows = await conn.fetch(
                    f"""
                    SELECT
                        username,
                        user_id,
                        level,
                        exp
                    FROM {table_name}
                    ORDER BY {order_column} DESC
                    LIMIT $1 OFFSET $2;
                    """,
                    quantity_int,
                    offset,
                )

        return jsonify([dict(row) for row in rows])

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/player_rank/<user_id>", methods=["GET"])
async def get_user_ranking(user_id: str):
    try:
        pool = await get_pool()

        async with pool.acquire() as conn:
            result = await conn.fetchrow(
                """
                SELECT
                    CASE
                        WHEN EXISTS (
                            SELECT 1
                            FROM total
                            WHERE user_id = $1
                        )
                        THEN (
                            SELECT COUNT(*) + 1
                            FROM total
                            WHERE level > (
                                SELECT level
                                FROM total
                                WHERE user_id = $1
                            )
                        )::TEXT
                        ELSE '???'
                    END AS rank;
                """,
                user_id,
            )

        if result:
            return jsonify({"user_id": user_id, "rank": result["rank"]})

        return jsonify({"error": "Unexpected error occurred"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/search/<input>", methods=["GET"])
async def search_player(input: str):
    try:
        encoded_input = urllib.parse.quote(input)

        async with aiohttp.ClientSession() as session:
            async with session.get(SEARCH_PROFILE_LINK + encoded_input) as search_response:
                data = await search_response.json()

        if isinstance(data, dict):
            data = [data]

        filtered_data = [
            entry
            for entry in data
            if entry.get("levels", {}).get("overall", {}).get("level", 0) >= 10
        ]

        return jsonify(filtered_data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


async def get_access_token(auth_code: str):
    token_url = "https://api.collab.land/oauth2/token"

    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "client_id": COLLAB_ID,
        "client_secret": COLLAB_SECRET,
        "redirect_uri": REDIRECT_URI,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(token_url, data=data) as response:
            return await response.json()


async def get_user_wallets(
    access_token: str,
    limit: int | None = None,
    pagination_token: str | None = None,
):
    wallets_url = "https://api.collab.land/account/wallets"

    params = {}

    if limit is not None:
        params["limit"] = limit

    if pagination_token is not None:
        params["paginationToken"] = pagination_token

    headers = {
        "x-api-key": COLLAB_KEY,
        "accept": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(wallets_url, headers=headers, params=params) as response:
            return await response.json()


async def look_for_profile(wallet_address: str):
    async with aiohttp.ClientSession() as session:
        return await profile_finder(session, wallet_address)


@app.route("/oauth2/callback", methods=["GET"])
async def oauth2_callback():
    auth_code = request.args.get("code")
    user_id = request.args.get("state")

    if not auth_code or not user_id:
        return redirect(url_for("error"))

    try:
        access_token_data = await get_access_token(auth_code)

        access_token = access_token_data.get("access_token")
        refresh_token = access_token_data.get("refresh_token")

        if not access_token:
            print(f"Collab.Land token response missing access_token: {access_token_data}")
            return redirect(url_for("error"))

        await add_collab_tokens(user_id, access_token, refresh_token)

        user_wallets_data = await get_user_wallets(access_token)

        addresses: list[str] = []
        player_ids: list[str] = []

        for wallet in user_wallets_data.get("items", []):
            wallet_type = wallet.get("walletType")

            if wallet_type not in {"evm", "metamask", "ronin"}:
                continue

            address = wallet.get("address")

            if not address:
                continue

            account_data = await look_for_profile(address)

            if account_data:
                addresses.append(address)
                player_id = account_data.get("_id")

                if player_id:
                    player_ids.append(player_id)

        if addresses and player_ids:
            formatted_addresses = " ".join(addresses)
            formatted_player_ids = " ".join(player_ids)

            await add_collab_wallets(
                user_id,
                formatted_addresses,
                formatted_player_ids,
            )

        print(f"User ID: {user_id}\nUser Wallets: {user_wallets_data}")

        return redirect(url_for("success"))

    except Exception as e:
        print(f"OAuth callback error: {e}")
        return redirect(url_for("error"))


@app.route("/success", methods=["GET"])
async def success():
    return await render_template_string(
        """
        <html>
        <body>
            <h1>Authorization successful!</h1>
            <script type="text/javascript">
                window.onload = function() {
                    window.open('', '_self', '');
                    window.close();
                    setTimeout(function() {
                        alert("Please return to Discord and refresh your accounts");
                    }, 1000);
                }
            </script>
        </body>
        </html>
        """
    )


@app.route("/error", methods=["GET"])
async def error():
    return "<h1>Error: Authorization code not found.</h1>"


@app.route("/", methods=["GET"])
@app.route("/about", methods=["GET"])
@app.route("/leaderboard", methods=["GET"])
@app.route("/home", methods=["GET"])
@app.route("/privacy", methods=["GET"])
@app.route("/terms", methods=["GET"])
@app.route("/discord", methods=["GET"])
async def serve_index():
    index_path = os.path.join(app.static_folder or "", "index.html")

    if app.static_folder and os.path.exists(index_path):
        return await send_from_directory(app.static_folder, "index.html")

    return jsonify(
        {
            "status": "backend running",
            "message": "frontend/build/index.html was not found",
        }
    ), 200


@app.route("/player/<player_id>", methods=["GET"])
async def serve_player_profile(player_id: str):
    print(f"Web Profile {player_id}")

    index_path = os.path.join(app.static_folder or "", "index.html")

    if app.static_folder and os.path.exists(index_path):
        return await send_from_directory(app.static_folder, "index.html")

    return jsonify(
        {
            "status": "backend running",
            "message": "frontend/build/index.html was not found",
            "player_id": player_id,
        }
    ), 200


@app.route("/player_data/<player_id>", methods=["GET"])
async def fetch_player_data(player_id: str):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(PROFILE_MID_LINK + player_id) as search_response:
                data = await search_response.json()

        return jsonify(data)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/<path:path>", methods=["GET"])
async def serve_static(path: str):
    if app.static_folder:
        static_path = os.path.join(app.static_folder, path)
        index_path = os.path.join(app.static_folder, "index.html")

        if path and os.path.exists(static_path):
            return await send_from_directory(app.static_folder, path)

        if os.path.exists(index_path):
            return await send_from_directory(app.static_folder, "index.html")

    return jsonify(
        {
            "status": "backend running",
            "message": "static file not found",
            "path": path,
        }
    ), 404


if __name__ == "__main__":
    app.run(
        host=os.getenv("SERVER_IP", SERVER_IP),
        port=int(os.getenv("PORT", "5050")),
        debug=True,
        use_reloader=False,
    )