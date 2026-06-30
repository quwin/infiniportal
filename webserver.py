from quart import Quart, request, redirect, url_for, render_template_string, jsonify, send_from_directory
from constants import REDIRECT_URI, COLLAB_ID, COLLAB_SECRET, COLLAB_KEY, SKILLS, SEARCH_PROFILE_LINK, PROFILE_MID_LINK, SERVER_IP
from database import add_collab_tokens, add_collab_wallets
from profile_utils import profile_finder
import urllib.parse
import aiohttp
import asyncio
import aiosqlite
import os

app = Quart(__name__, static_folder='frontend/build', static_url_path='')

DATABASE = 'leaderboard.db'


async def get_db():
    conn = await aiosqlite.connect(DATABASE)
    conn.row_factory = aiosqlite.Row
    return conn

@app.route('/leaderboard/<table_name>/<order>/<page_number>/<quantity>',
           defaults={'guild_name': None},
           methods=['GET'])
@app.route('/leaderboard/<table_name>/<order>/<page_number>/<quantity>/<guild_name>',
           methods=['GET'])
async def get_leaderboard(table_name, order, page_number, quantity, guild_name=None):
    valid_orders = ['level', 'exp']
    valid_tables = SKILLS.copy()
    valid_tables.append('total')

    try:
        int(quantity)
        int(page_number)
    except ValueError:
        return jsonify({'error': 'Invalid quantity or page number'}), 400

    if order not in valid_orders or table_name not in valid_tables:
        return jsonify({'error': 'Invalid table name or order'}), 400

    offset = int(quantity) * (int(page_number) - 1)

    try:
        db = await get_db()
        if guild_name:
            cursor1 = await db.execute(
                '''
                SELECT id
                FROM guilds
                WHERE handle = ?''', (guild_name, ))
            id = await cursor1.fetchone()

            if id:
                cursor = await db.execute(
                    f'''
                    SELECT u.username, u.user_id, u.level, u.exp
                    FROM {table_name} u
                    JOIN guild_{id[0]} gm ON gm.user_id = u.user_id
                    ORDER BY u.{order} DESC
                    LIMIT {str(quantity)} OFFSET ?''', (offset, ))
            else:
                cursor = await db.execute(
                    f'''
                    SELECT username, user_id level, exp
                    FROM {table_name}
                    ORDER BY {order} DESC
                    LIMIT {str(quantity)} OFFSET ?''', (offset, ))
        else:
            cursor = await db.execute(
                f'''
                SELECT username, user_id ,level, exp
                FROM {table_name}
                ORDER BY {order} DESC
                LIMIT {str(quantity)} OFFSET ?''', (offset, ))

        rows = await cursor.fetchall()
        await db.close()
        return jsonify([dict(row) for row in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
            
@app.route('/player_rank/<user_id>', methods=['GET'])
async def get_user_ranking(user_id):
    try:
        db = await get_db()
        cursor = await db.execute(
            '''
            SELECT 
                CASE
                    WHEN EXISTS (SELECT 1 FROM total WHERE user_id = ?) 
                    THEN (
                        SELECT COUNT(*) + 1
                        FROM total
                        WHERE level > (SELECT level FROM total WHERE user_id = ?)
                    )
                    ELSE '???'
                END as rank
            ''', (user_id, user_id)
        )
        result = await cursor.fetchone()
        await db.close()
        if result:
            return jsonify({'user_id': user_id, 'rank': result['rank']})
        else:
            return jsonify({'error': 'Unexpected error occurred'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500        


@app.route('/search/<input>', methods=['GET'])
async def search_player(input):
    try:
        encoded_input = urllib.parse.quote(input)
        async with aiohttp.ClientSession() as session, session.get(SEARCH_PROFILE_LINK + encoded_input) as search_response:
            data = await search_response.json()
            if isinstance(data, dict):
                data = [data]
            # Filter out entries where the overall level is less than 10
            filtered_data = [entry for entry in data if entry['levels']['overall']['level'] >= 10]
            return jsonify(filtered_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

async def get_access_token(auth_code):
    token_url = "https://api.collab.land/oauth2/token"
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "client_id": COLLAB_ID,
        "client_secret": COLLAB_SECRET,
        "redirect_uri": REDIRECT_URI,
    }
    async with aiohttp.ClientSession() as session, session.post(
            token_url, data=data) as response:
        return await response.json()


# Request linked wallet(s) from Collab.land API
async def get_user_wallets(access_token, limit=None, pagination_token=None):
    wallets_url = "https://api.collab.land/account/wallets"
    params = {}
    if limit is not None:
        params['limit'] = limit
    if pagination_token is not None:
        params['paginationToken'] = pagination_token

    headers = {
        'x-api-key': COLLAB_KEY,
        'accept': 'application/json',
        'Authorization': f"Bearer {access_token}"
    }

    async with aiohttp.ClientSession() as session, session.get(
            wallets_url, headers=headers, params=params) as response:
        return await response.json()


# Async wrapper for looking for a given profile from their address from the Pixels.xyz API
async def look_for_profile(wallet_address):
    async with aiohttp.ClientSession() as session:
        return await profile_finder(session, wallet_address)


@app.route("/oauth2/callback")
def oauth2_callback():
    auth_code = request.args.get("code")
    user_id = request.args.get("state")
    if auth_code and user_id:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        access_token_data = loop.run_until_complete(
            get_access_token(auth_code))

        access_token = access_token_data.get("access_token")
        refresh_token = access_token_data.get("refresh_token")
        loop.run_until_complete(
            add_collab_tokens(user_id, access_token, refresh_token))

        user_wallets_data = loop.run_until_complete(
            get_user_wallets(access_token))
        addresses = []
        player_ids = []

        for wallet in user_wallets_data.get("items", []):
            type = wallet.get("walletType")
            if type == 'evm' or type == 'metamask' or type == 'ronin':
                address = wallet.get("address")
                account_data = loop.run_until_complete(
                    look_for_profile(address))
                if address and account_data:
                    addresses.append(address)
                    player_ids.append(account_data.get("_id"))

        if addresses and player_ids:
            formatted_addresses = " ".join(addresses)
            formatted_player_ids = " ".join(player_ids)
            loop.run_until_complete(
                add_collab_wallets(user_id, formatted_addresses,
                                   formatted_player_ids))

        print(f"User ID: \n{user_id}, \n User Wallets: \n{user_wallets_data}")
        return redirect(url_for('success'))
    else:
        return redirect(url_for('error'))


@app.route("/success")
def success():
    return render_template_string("""
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
    """)


@app.route("/error")
def error():
    return "<h1>Error: Authorization code not found.</h1>"


# Serve static files
@app.route('/')
@app.route('/about')
@app.route('/leaderboard')
@app.route('/home')
@app.route('/privacy')
@app.route('/terms')
@app.route('/discord')
async def serve_index():
    if app.static_folder:
        return await send_from_directory(app.static_folder, 'index.html')
    else:
        return 'Static folder not configured'

@app.route('/player/<player_id>')
async def serve_player_profile(player_id):
    print(f"Web Profile {player_id}")
    if app.static_folder:
        return await send_from_directory(app.static_folder, 'index.html')
    else:
        return 'Static folder not configured'

@app.route('/player_data/<player_id>')
async def fetch_player_data(player_id):
    try:
        async with aiohttp.ClientSession() as session, session.get(PROFILE_MID_LINK + player_id) as search_response:
            data = await search_response.json()
            return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/<path:path>')
async def serve_static(path):
    if app.static_folder:
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return await send_from_directory(app.static_folder, path)
        else:
            return await send_from_directory(app.static_folder, 'index.html')
    else:
        return 'Static folder not configured'


if __name__ == "__main__":
    app.run(host=SERVER_IP, port=5050, debug=True, use_reloader=False)
