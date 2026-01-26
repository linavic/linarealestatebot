import os
import re
import requests
import logging
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

def get_env(name):
    val = os.environ.get(name)
    return val.strip() if val else None

API_KEY = get_env("GEMINI_API_KEY")
TELEGRAM_TOKEN = get_env("TELEGRAM_TOKEN")
ADMIN_ID = get_env("ADMIN_ID")

# רשימת מודלים לגיבוי - אם אחד נכשל, ננסה את הבא
MODELS = [
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash-exp", # מודל חדש ומהיר
    "gemini-1.0-pro"
]

def notify_lina(text):
    if not TELEGRAM_TOKEN or not ADMIN_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": ADMIN_ID, "text": text, "parse_mode": "HTML"}, timeout=3)
    except: pass

@app.route("/")
def home():
    return "Lina Smart-Lead Bot 🚀", 200

@app.route("/web-chat", methods=["POST"])
def web_chat():
    if not API_KEY:
        return jsonify({"reply": "תקלה טכנית."}), 500

    try:
        data = request.get_json(force=True)
        msg = data.get("message", "").strip()
    except:
        return jsonify({"reply": ""}), 400

    if not msg: return jsonify({"reply": "היי 👋"}), 200

    # === תיקון הטמטום: זיהוי טלפון ===
    # אם הלקוח שלח טלפון - אנחנו לא שואלים את גוגל! אנחנו עונים מיד.
    clean_msg = msg.replace('-', '').replace(' ', '')
    if re.search(r'\d{9,10}', clean_msg):
        # 1. שולחים לך לטלגרם
        notify_lina(f"🔥 <b>ליד חם! הושאר טלפון:</b>\n{msg}")
        
        # 2. עונים ללקוח מיד (בלי AI שעלול ליפול)
        return jsonify({"reply": "מעולה! קיבלתי את המספר, לינה תחזור אליך בהקדם. 😊"}), 200

    # === אם אין טלפון, מנסים לדבר עם ה-AI ===
    notify_lina(f"💬 <b>הודעה באתר:</b>\n{msg}")

    prompt = f"""
    You are Lina's real estate assistant.
    User said: "{msg}"
    RULES:
    1. Reply in the SAME language (Hebrew/Russian/English).
    2. Be short and polite.
    3. Your GOAL: Ask for Name and Phone.
    4. NO internal thoughts.
    """

    # לולאת ניסיונות - מנסה מודלים עד שמצליח
    for model in MODELS:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}"
            response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=8)
            
            if response.status_code == 200:
                result = response.json()
                reply = result["candidates"][0]["content"]["parts"][0]["text"]
                # ניקוי רעשים
                reply = re.sub(r'thought_.*?(\n|$)', '', reply, flags=re.IGNORECASE).strip()
                return jsonify({"reply": reply}), 200
            else:
                logger.warning(f"Model {model} failed: {response.status_code}")
                continue # נסה את המודל הבא ברשימה
        except Exception as e:
            logger.error(f"Error on {model}: {e}")
            continue

    # אם כל המודלים נכשלו (וזה כמעט בלתי אפשרי), רק אז הודעת שגיאה
    return jsonify({"reply": "אני מעדכן את לינה על פנייתך. תודה!"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
