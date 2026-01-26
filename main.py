import os
import logging
import threading
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

def get_key(name):
    val = os.environ.get(name)
    return val.strip() if val else None

API_KEY = get_key("GEMINI_API_KEY")
TELEGRAM_TOKEN = get_key("TELEGRAM_TOKEN")
ADMIN_ID = get_key("ADMIN_ID")

chat_history = {}
CURRENT_MODEL = None

def get_working_model():
    global CURRENT_MODEL
    if CURRENT_MODEL:
        return CURRENT_MODEL

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()

        preferred = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.0-pro", "gemini-pro"]
        available_models = [
            m['name'].replace('models/', '')
            for m in data.get('models', [])
            if 'generateContent' in m.get('supportedGenerationMethods', [])
        ]

        for pref in preferred:
            for avail in available_models:
                if pref in avail:
                    CURRENT_MODEL = avail
                    logger.info(f"Using model: {CURRENT_MODEL}")
                    return CURRENT_MODEL

        if available_models:
            CURRENT_MODEL = available_models[0]
            logger.warning(f"Using fallback model: {CURRENT_MODEL}")
            return CURRENT_MODEL

    except Exception as e:
        logger.error(f"Error scanning models: {e}")

    CURRENT_MODEL = "gemini-1.5-flash"
    return CURRENT_MODEL

def notify_lina(text):
    if not TELEGRAM_TOKEN or not ADMIN_ID:
        logger.warning("TELEGRAM_TOKEN or ADMIN_ID missing – cannot send Telegram notification")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": ADMIN_ID, "text": text}
        r = requests.post(url, json=payload, timeout=5)
        if r.status_code != 200:
            logger.error(f"Telegram error {r.status_code}: {r.text}")
    except Exception as e:
        logger.exception(f"Failed to send Telegram message: {e}")

@app.route('/')
def home():
    return "Lina Bot Auto-Fix Active 🚀"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    try:
        if not API_KEY:
            return jsonify({'reply': "Server error: missing API key"}), 500

        data = request.json or {}
        msg = data.get('message', '') or ''
        uid = data.get('user_id', 'guest')

        logger.info(f"Incoming message from {uid}: {msg}")

        clean_msg = re.sub(r'[s-]', '', msg)
        # טלפון ישראלי בסיסי: 0 + 8–9 ספרות
        phone_match = re.search(r'0d{8,9}', clean_msg)

        if phone_match:
            text = f"✅ יש ליד חדש!
User ID: {uid}
Message: {msg}
Phone: {phone_match.group(0)}"
            threading.Thread(target=notify_lina, args=(text,)).start()
        else:
            threading.Thread(target=notify_lina, args=(f"💬 {uid}: {msg}",)).start()

        model_name = get_working_model()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"

        history = chat_history.get(uid, [])
        history.append({"role": "user", "parts": [{"text": msg}]})

        system_prompt = (
            "You are Lina's real estate assistant. "
            "Reply in the SAME language as the user. "
            "Your goal is to get the user's full name and phone number. "
            "Be short and conversational. "
            "Never show internal reasoning."
        )

        contents = [
            {"role": "user", "parts": [{"text": system_prompt}]},
        ]
        for h in history[-5:]:
            contents.append(h)

        payload = {"contents": contents}

        resp = requests.post(url, json=payload,
                             headers={'Content-Type': 'application/json'}, timeout=15)

        if resp.status_code != 200:
            logger.error(f"Gemini HTTP error {resp.status_code}: {resp.text}")
            return jsonify({'reply': "אשמח לעזור! אנא השאר שם וטלפון ואחזור אליך בהקדם."})

        result = resp.json()
        if "error" in result:
            logger.error(f"Gemini API error: {result['error']}")
            return jsonify({'reply': "תקלה זמנית במערכת. אפשר לכתוב כאן שם וטלפון ואני אחזור בהקדם."})

        candidates = result.get('candidates', [])
        if not candidates:
            logger.warning("No candidates returned from Gemini")
            return jsonify({'reply': "אשמח לעזור! אנא כתוב/כתבי שם וטלפון."})

        bot_text = candidates[0]['content']['parts'][0].get('text', '')

        bot_text = re.sub(r'thought_.*?(
|$)', '', bot_text, flags=re.IGNORECASE)
        bot_text = bot_text.replace("Option 1", "").replace("Analysis:", "")

        history.append({"role": "model", "parts": [{"text": bot_text}]})
        chat_history[uid] = history[-10:]

        return jsonify({'reply': bot_text})

    except Exception as e:
        logger.exception(f"Server Error in /web-chat: {e}")
        return jsonify({'reply': "תקלה טכנית. נא להשאיר שם וטלפון ואחזור אליך בהקדם."}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
