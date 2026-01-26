import os
import logging
import threading
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import requests

# הגדרת לוגים חזקה יותר שתופיע מיד ב-Render
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# קריאת מפתחות
GENAI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")

# חיבור ל-Gemini
model = None
if GENAI_API_KEY:
    try:
        genai.configure(api_key=GENAI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")
        print("✅ Gemini Configured")
    except Exception as e:
        print(f"❌ Gemini Config Error: {e}")
else:
    print("⚠️ MISSING GEMINI_API_KEY")

chat_sessions = {}

# פונקציית שליחה לטלגרם (עם הדפסת שגיאות)
def send_tele(text):
    if not TELEGRAM_TOKEN or not ADMIN_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": ADMIN_ID, "text": text}, timeout=5)
    except Exception as e:
        print(f"❌ Telegram Error: {e}")

@app.route('/')
def home():
    return "Debug Mode Active"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    try:
        # 1. בדיקת מפתח
        if not GENAI_API_KEY:
            return jsonify({'reply': "שגיאה קריטית: חסר המפתח GEMINI_API_KEY בהגדרות השרת."})
        
        # 2. בדיקת חיבור למודל
        if not model:
            return jsonify({'reply': "שגיאה: המודל לא נטען. המפתח כנראה שגוי."})

        data = request.json
        user_msg = data.get('message')
        user_id = data.get('user_id', 'guest')

        # 3. ניסיון דיווח ללינה
        threading.Thread(target=send_tele, args=(f"לקוח: {user_msg}",)).start()

        # 4. התחלת שיחה
        if user_id not in chat_sessions:
            chat_sessions[user_id] = model.start_chat(history=[])
        
        # 5. שליחה ל-Google (כאן לרוב זה נופל)
        chat = chat_sessions[user_id]
        response = chat.send_message(user_msg)
        
        return jsonify({'reply': response.text})

    except Exception as e:
        # === כאן השינוי: הבוט יגיד לך מה השגיאה ===
        error_msg = str(e)
        print(f"❌ CRITICAL ERROR: {error_msg}")
        return jsonify({'reply': f"🔴 שגיאה טכנית (צלמי מסך ושלחי לבונה האתר):\n{error_msg}"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
