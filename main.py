import os
import re
import requests
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

# הגדרת logging - כדי שנראה ב-Render מה קורה
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# פתיחת גישה לכל הדומיינים (מונע בעיות CORS)
CORS(app, resources={r"/*": {"origins": "*"}})

# פונקציה לקריאת משתני סביבה עם ניקוי רווחים
def get_env(name):
    v = os.environ.get(name)
    if v:
        v = v.strip() # מחיקת רווחים מיותרים
        logger.info(f"Environment variable {name}: SET")
    else:
        logger.warning(f"Environment variable {name}: NOT FOUND")
    return v

# קריאת משתני סביבה
API_KEY = get_env("GEMINI_API_KEY")
TELEGRAM_TOKEN = get_env("TELEGRAM_TOKEN")
ADMIN_ID = get_env("ADMIN_ID")

# שימוש במודל היציב
MODEL = "gemini-1.5-flash"

def notify_lina(text):
    """שליחת התראה לטלגרם"""
    if not TELEGRAM_TOKEN or not ADMIN_ID:
        logger.warning("Telegram credentials missing - notification skipped")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        response = requests.post(
            url,
            json={
                "chat_id": ADMIN_ID,
                "text": text,
                "parse_mode": "HTML"
            },
            timeout=5
        )
        response.raise_for_status()
        logger.info("Telegram notification sent successfully")
        return True
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

@app.route("/")
def home():
    """בדיקת תקינות השרת"""
    return "Lina Bot is Running! 🚀", 200

@app.route("/web-chat", methods=["POST", "OPTIONS"])
def web_chat():
    # טיפול ב-CORS preflight
    if request.method == "OPTIONS":
        return "", 204
    
    # בדיקת API key
    if not API_KEY:
        logger.error("API_KEY missing")
        return jsonify({"reply": "תקלה טכנית בשרת (חסר מפתח)."}), 500

    # קריאת הנתונים
    try:
        data = request.get_json(force=True)
        msg = data.get("message", "").strip()
    except Exception as e:
        return jsonify({"reply": "אנא נסי שוב."}), 400

    if not msg:
        return jsonify({"reply": "היי! איך אפשר לעזור לך היום? 😊"}), 200

    logger.info(f"Received message: {msg}")

    # זיהוי מספר טלפון ושליחה ללינה
    phone_pattern = r'\b0\d{1,2}[-\s]?\d{7}\b|\b\d{9,10}\b'
    if re.search(phone_pattern, msg):
        notify_lina(f"🔥 <b>ליד חם! הושאר טלפון:</b>\n{msg}")
    else:
        notify_lina(f"💬 <b>הודעה באתר:</b>\n{msg}")

    # הכנת ה-prompt למוח של גוגל
    prompt = f"""You are a real estate assistant for Lina.
    INSTRUCTIONS:
    1. Reply in the same language as the user (Hebrew/Russian/English).
    2. Be short, polite, and professional.
    3. YOUR GOAL: Get the user's Name and Phone Number.
    4. Do NOT explain your logic. Do NOT say 'thought'. Just reply.
    
    User message: {msg}
    """

    # קריאה ישירה לגוגל
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            reply = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            # ניקוי רעשים למקרה שגוגל מזייף
            reply = reply.replace("thought", "").replace("Analysis", "")
            return jsonify({"reply": reply}), 200
        else:
            logger.error(f"Google Error: {response.text}")
            return jsonify({"reply": "אשמח לעזור! תשאירי לי שם וטלפון ואחזור אלייך בהקדם."}), 200

    except Exception as e:
        logger.error(f"Server Error: {e}")
        return jsonify({"reply": "אשמח לעזור! תשאירי לי שם וטלפון ואחזור אלייך בהקדם."}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
