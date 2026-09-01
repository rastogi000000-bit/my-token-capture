from flask import Flask, request, jsonify, Response
import requests
import os
import re
import json

app = Flask(__name__)
REAL_SERVER = os.environ.get('REAL_SERVER_URL', 'https://client.ind.freefiremobile.com')

@app.route('/user/<user_id>/', defaults={'subpath': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@app.route('/user/<user_id>/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def proxy(user_id, subpath):
    if subpath:
        real_url = f"{REAL_SERVER}/{subpath}"
    else:
        real_url = f"{REAL_SERVER}/"

    print(f"\n🔹 Proxying {request.method} {real_url}")

    headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'connection']}
    headers.pop('Content-Length', None)
    headers['Host'] = REAL_SERVER.replace('https://', '').split('/')[0]

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

    # ── Log full response ──
    try:
        data = resp.json()
        print(f"   JSON response (first 500 chars):\n{json.dumps(data, indent=2)[:500]}")
        # Search for any key with 'token' or 'access'
        for key in data:
            if 'token' in key.lower() or 'access' in key.lower():
                print(f"🔑 Found '{key}': {data[key][:40]}...")
    except:
        raw = resp.text
        print(f"   Raw response (first 300 chars): {raw[:300]}...")
        # Also search hex pattern
        hex_pattern = re.compile(r'[0-9a-fA-F]{64}')
        matches = hex_pattern.findall(raw)
        if matches:
            print(f"✅ HEX TOKEN FOUND IN RAW: {matches[0]}")

    # ── Return the real server's response ──
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