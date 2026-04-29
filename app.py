import os
import json
import requests
import hashlib
import hmac
from flask import Flask, request, jsonify

app = Flask(__name__)

# ── Config ──────────────────────────────────────────────
TELEGRAM_TOKEN     = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID")
STRAVA_CLIENT_ID   = os.environ.get("STRAVA_CLIENT_ID")
STRAVA_CLIENT_SECRET = os.environ.get("STRAVA_CLIENT_SECRET")
STRAVA_VERIFY_TOKEN  = os.environ.get("STRAVA_VERIFY_TOKEN", "myverifytoken123")
GEMINI_API_KEY     = os.environ.get("GEMINI_API_KEY")

# ── Strava helpers ───────────────────────────────────────
def get_strava_token():
    """Read saved access token from file."""
    try:
        with open("strava_token.json") as f:
            data = json.load(f)
        # Refresh if expired
        import time
        if data["expires_at"] < time.time():
            r = requests.post("https://www.strava.com/oauth/token", data={
                "client_id":     STRAVA_CLIENT_ID,
                "client_secret": STRAVA_CLIENT_SECRET,
                "grant_type":    "refresh_token",
                "refresh_token": data["refresh_token"],
            })
            data = r.json()
            with open("strava_token.json", "w") as f:
                json.dump(data, f)
        return data["access_token"]
    except Exception as e:
        print(f"Token error: {e}")
        return None

def get_activity(activity_id):
    token = get_strava_token()
    if not token:
        return None
    r = requests.get(
        f"https://www.strava.com/api/v3/activities/{activity_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    return r.json() if r.status_code == 200 else None

# ── Gemini AI analysis ───────────────────────────────────
def analyze_with_gemini(activity):
    name        = activity.get("name", "فعالیت")
    sport       = activity.get("sport_type", activity.get("type", "ناشناخته"))
    distance_km = round(activity.get("distance", 0) / 1000, 2)
    duration_s  = activity.get("moving_time", 0)
    duration_min = round(duration_s / 60, 1)
    elevation   = activity.get("total_elevation_gain", 0)
    avg_hr      = activity.get("average_heartrate")
    max_hr      = activity.get("max_heartrate")
    avg_speed   = round(activity.get("average_speed", 0) * 3.6, 1)  # m/s → km/h
    suffer_score = activity.get("suffer_score")
    kudos       = activity.get("kudos_count", 0)

    # Pace for running
    pace_str = ""
    if distance_km > 0 and sport in ("Run", "TrailRun", "VirtualRun"):
        pace_sec = duration_s / distance_km
        pace_min = int(pace_sec // 60)
        pace_s   = int(pace_sec % 60)
        pace_str = f"- پیس میانگین: {pace_min}:{pace_s:02d} دقیقه/کیلومتر\n"

    prompt = f"""یه مربی دو و ورزش هستی. فعالیت زیر رو به فارسی تحلیل کن و بازخورد مفید بده.

اطلاعات فعالیت:
- نام: {name}
- نوع: {sport}
- مسافت: {distance_km} کیلومتر
- زمان: {duration_min} دقیقه
- اختلاف ارتفاع: {elevation} متر
- سرعت میانگین: {avg_speed} کیلومتر/ساعت
{pace_str}- ضربان قلب میانگین: {avg_hr if avg_hr else 'نامشخص'}
- ضربان قلب حداکثر: {max_hr if max_hr else 'نامشخص'}
- امتیاز فشار: {suffer_score if suffer_score else 'نامشخص'}
- کودوس: {kudos}

لطفاً در قالب زیر پاسخ بده:
1. 📊 خلاصه عملکرد (۲-۳ جمله)
2. 💪 نقاط قوت
3. 🎯 پیشنهاد بهبود
4. 🔄 توصیه برای تمرین بعدی

پاسخ رو کوتاه، واضح و انگیزشی بنویس."""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    r = requests.post(url, json=body)
    if r.status_code == 200:
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    print(f"Gemini error: {r.text}")
    return "تحلیل در دسترس نیست."

# ── Telegram sender ──────────────────────────────────────
def send_telegram(text):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id":    TELEGRAM_CHAT_ID,
            "text":       text,
            "parse_mode": "Markdown",
        }
    )

# ── Routes ───────────────────────────────────────────────
@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """Strava webhook verification."""
    mode      = request.args.get("hub.mode")
    token     = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == STRAVA_VERIFY_TOKEN:
        return jsonify({"hub.challenge": challenge})
    return "Forbidden", 403

@app.route("/webhook", methods=["POST"])
def receive_webhook():
    """Handle new Strava activity."""
    data = request.json
    print(f"Webhook received: {data}")

    if data.get("object_type") == "activity" and data.get("aspect_type") == "create":
        activity_id = data.get("object_id")
        activity    = get_activity(activity_id)

        if activity:
            sport    = activity.get("sport_type", activity.get("type", "فعالیت"))
            distance = round(activity.get("distance", 0) / 1000, 2)
            name     = activity.get("name", "فعالیت جدید")

            send_telegram(f"🏃 *فعالیت جدید ثبت شد!*\n_{name}_ — {distance} کم — {sport}\n\nدر حال تحلیل... ⏳")

            analysis = analyze_with_gemini(activity)
            send_telegram(f"📈 *تحلیل فعالیت:*\n\n{analysis}")
        else:
            send_telegram("⚠️ فعالیت جدید ثبت شد ولی اطلاعاتش در دسترس نیست.")

    return "OK", 200

@app.route("/auth")
def auth():
    """Strava OAuth - step 1: redirect."""
    url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={STRAVA_CLIENT_ID}"
        f"&redirect_uri=https://{request.host}/callback"
        f"&response_type=code"
        f"&scope=activity:read_all"
    )
    return f'<a href="{url}">Click here to authorize Strava</a>'

@app.route("/callback")
def callback():
    """Strava OAuth - step 2: exchange code for token."""
    code = request.args.get("code")
    r = requests.post("https://www.strava.com/oauth/token", data={
        "client_id":     STRAVA_CLIENT_ID,
        "client_secret": STRAVA_CLIENT_SECRET,
        "code":          code,
        "grant_type":    "authorization_code",
    })
    token_data = r.json()
    with open("strava_token.json", "w") as f:
        json.dump(token_data, f)
    athlete = token_data.get("athlete", {})
    name    = f"{athlete.get('firstname','')} {athlete.get('lastname','')}".strip()
    send_telegram(f"✅ استراوا با موفقیت وصل شد!\nخوش اومدی {name} 🎉")
    return f"✅ Authorization successful! Welcome {name}. You can close this tab."

@app.route("/")
def index():
    return "🏃 Strava Telegram Bot is running!"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
