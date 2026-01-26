import os
import re
import requests
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app)

def get_env(name):
    v = os.environ.get(name)
    return v.strip() if v else None

API_KEY = get_env("GEMINI_API_KEY")
TELEGRAM_TOKEN = get_env("TELEGRAM_TOKEN")
ADMIN_ID = get_env("ADMIN_ID")

MODEL = "gemini-1.5-flash"

def notify_lina(text):
    if not TELEGRAM_TOKEN or not ADMIN_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={
                "chat_id": ADMIN_ID,
                "text": text
            },
            timeout=3
        )
    except Exception as e:
        logging.warning(f"Telegram error: {e}")

@app.route("/")
def home():
    return "Lina Bot Running ✅"

@app.route("/web-chat", methods=["POST"])
def web_chat():
    if not API_KEY:
        return jsonify({"reply": "System error."})

    data = request.json or {}
    msg = data.get("message", "").strip()

    if not msg:
        return jsonify({"reply": "איך אפשר לעזור?"})

    # זיהוי טלפון
    clean = re.sub(r"[^\d]", "", msg)
    if re.search(r"\d{9,10}", clean):
        notify_lina(f"📞 ליד חדש:\n{msg}")
    else:
        notify_lina(f"💬 הודעה:\n{msg}")

    prompt = f"""
You are a real estate assistant for Lina.
Reply ONLY in the same language as the user.
Be short, friendly and professional.
Your goal is to get the user's NAME and PHONE NUMBER.
Do not explain anything.
Do not give options.
Just ask naturally.

User message:
{msg}
""".strip()

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ]
    }

    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        data = r.json()

        reply = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )

        if not reply:
            raise ValueError("Empty reply")

        return jsonify({"reply": reply})

    except Exception as e:
        logging.error(f"Gemini error: {e}")
        return jsonify({
            "reply": "אשמח לעזור 😊 אשאירי שם וטלפון ואחזור אליך בהקדם."
        })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
