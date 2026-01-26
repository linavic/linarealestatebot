import os
import logging
import threading
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import requests

# הגדרת לוגים שתופיע מיד
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app)

# === קבלת מפתחות עם ניקוי רווחים (טעות נפוצה) ===
def get_key(name):
    val = os.environ.get(name)
    if val:
        return val.strip()
    return None

GENAI_API_KEY = get_key("GEMINI_API_KEY")
TELEGRAM_TOKEN = get_key("TELEGRAM_TOKEN")
ADMIN_ID = get_key("ADMIN_ID")

# === בדיקת חיבור ל-Gemini ===
model = None
gemini_status = "Not Connected"

if GENAI_API_KEY:
    try:
        genai.configure(api_key=GENAI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        gemini_status = "Connected ✅"
    except Exception as e:
        gemini_status = f"Error: {str(e)}"
else:
    gemini_status = "Missing API Key ❌"

# פונקציית שליחה לטלגרם (מוגנת מקריסות)
def send_telegram_safe(text):
    if not TELEGRAM_TOKEN or not ADMIN_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": ADMIN_ID, "text": text}, timeout=3)
    except: pass

@app.route('/')
def home():
    return f"Status: {gemini_status}"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    try:
        # בדיקה 1: האם יש מפתח?
        if not GENAI_API_KEY:
            return jsonify({'reply': "🔴 שגיאה: חסר מפתח GEMINI_API_KEY בהגדרות השרת (Environment)."})
        
        # בדיקה 2: האם המודל נטען?
        if not model:
            return jsonify({'reply': f"🔴 שגיאה בחיבור לגוגל: {gemini_status}"})

        data = request.json
        user_msg = data.get('message')
        
        # בדיקה 3: שליחה לטלגרם (בלי לתקוע)
        threading.Thread(target=send_telegram_safe, args=(f"לקוח: {user_msg}",)).start()

        # בדיקה 4: שליחה למודל (כאן זה בדרך כלל נופל)
        response = model.generate_content(user_msg)
        
        return jsonify({'reply': response.text})

    except Exception as e:
        # === זה החלק החשוב: הבוט יגיד לך מה הבעיה ===
        error_message = str(e)
        print(f"ERROR: {error_message}")
        return jsonify({'reply': f"🔴 דוח שגיאה (צלמי מסך):\n{error_message}"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
