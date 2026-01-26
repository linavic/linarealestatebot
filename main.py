import os
import re
import requests
import logging
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

# משתנה גלובלי לשמירת המודל שעובד
CURRENT_MODEL_URL = None

def get_working_google_url():
    """סורק את החשבון ומוצא מודל פעיל"""
    global CURRENT_MODEL_URL
    if CURRENT_MODEL_URL: return CURRENT_MODEL_URL

    logger.info("🔍 Scanning for available Google models...")
    try:
        # בקשה לרשימת המודלים הפתוחים בחשבון
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
        resp = requests.get(list_url, timeout=5)
        
        if resp.status_code == 200:
            data = resp.json()
            # מחפש מודל שיודע לייצר טקסט
            for model in data.get('models', []):
                name = model['name']
                methods = model.get('supportedGenerationMethods', [])
                if 'generateContent' in methods:
                    # מנקה את הקידומת models/ אם קיימת
                    clean_name = name.replace('models/', '')
                    logger.info(f"✅ FOUND WORKING MODEL: {clean_name}")
                    
                    # בניית הכתובת הסופית
                    CURRENT_MODEL_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{clean_name}:generateContent?key={API_KEY}"
                    return CURRENT_MODEL_URL
    except Exception as e:
        logger.error(f"Scan error: {e}")

    # ברירת מחדל למקרה חירום (אם הסריקה נכשלה)
    logger.warning("⚠️ Scan failed, forcing default model")
    return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"

def notify_lina(text):
    if not TELEGRAM_TOKEN or not ADMIN_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": ADMIN_ID, "text": text, "parse_mode": "HTML"}, timeout=3)
    except: pass

@app.route("/")
def home():
    return "Lina Auto-Scanner Bot 🚀", 200

@app.route("/web-chat", methods=["POST"])
def web_chat():
    if not API_KEY:
        return jsonify({"reply": "שגיאת שרת: חסר מפתח."}), 500

    try:
        data = request.get_json(force=True)
        msg = data.get("message", "").strip()
    except:
        return jsonify({"reply": ""}), 400

    if not msg: return jsonify({"reply": "היי 👋"}), 200

    # 1. זיהוי טלפון ושליחה ללינה
    phone_pattern = r'\b0\d{1,2}[-\s]?\d{7}\b|\b\d{9,10}\b'
    if re.search(phone_pattern, msg):
        notify_lina(f"🔥 <b>ליד חם! הושאר טלפון:</b>\n{msg}")
    else:
        notify_lina(f"💬 <b>לקוח באתר:</b>\n{msg}")

    # 2. השגת כתובת דינמית (מונע שגיאות 404)
    target_url = get_working_google_url()

    # 3. הכנת ההוראה לבוט
    prompt = f"""
    You are Lina's real estate assistant.
    User input: "{msg}"
    
    INSTRUCTIONS:
    - Reply in the SAME language as the user.
    - Be short, friendly, and professional.
    - Ask for their Name and Phone Number.
    - CRITICAL: Do NOT show internal thoughts. Just the reply.
    """

    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }

    try:
        # שליחה לגוגל
        response = requests.post(target_url, json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            try:
                reply = result["candidates"][0]["content"]["parts"][0]["text"]
                
                # === מספריים: ניקוי מחשבות ===
                # מוחק כל טקסט שמתחיל ב-thought או נראה כמו ניתוח
                reply = re.sub(r'thought_.*?(\n|$)', '', reply, flags=re.IGNORECASE)
                reply = reply.replace("Analysis:", "").strip()
                
                return jsonify({"reply": reply}), 200
            except:
                return jsonify({"reply": "תוכל לחזור על זה?"}), 200
        else:
            # אם יש שגיאה, נדפיס אותה ללוג ב-Render כדי שנבין
            logger.error(f"GOOGLE ERROR: {response.text}")
            return jsonify({"reply": "אשמח לעזור! אנא השאר שם וטלפון ואחזור אליך."}), 200

    except Exception as e:
        logger.error(f"SERVER ERROR: {e}")
        return jsonify({"reply": "אשמח לעזור! אנא השאר פרטים ליצירת קשר."}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
