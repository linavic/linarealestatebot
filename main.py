import os
import logging
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import requests

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app)

# === קבלת מפתחות ===
def get_key(name):
    val = os.environ.get(name)
    return val.strip() if val else None

GENAI_API_KEY = get_key("GEMINI_API_KEY")
TELEGRAM_TOKEN = get_key("TELEGRAM_TOKEN")
ADMIN_ID = get_key("ADMIN_ID")

# === חיבור למוח (Gemini) ===
model = None
if GENAI_API_KEY:
    try:
        genai.configure(api_key=GENAI_API_KEY)
        # שינוי קריטי: שימוש במודל gemini-pro היציב
        model = genai.GenerativeModel("gemini-pro")
        print("✅ Gemini PRO Connected")
    except Exception as e:
        print(f"❌ Gemini Error: {e}")

chat_sessions = {}

# פונקציית שליחה לטלגרם (בלי לתקוע את האתר)
def send_telegram_background(text):
    if not TELEGRAM_TOKEN or not ADMIN_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": ADMIN_ID, "text": text}, timeout=4)
    except: pass

@app.route('/')
def home():
    return "Lina Bot is Ready! 🚀"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    try:
        if not model:
            return jsonify({'reply': "שגיאת מערכת: המוח לא מחובר."})

        data = request.json
        user_msg = data.get('message')
        user_id = data.get('user_id', 'guest')

        # 1. שליחת התראה ללינה ברקע
        threading.Thread(target=send_telegram_background, args=(f"👤 *לקוח:* {user_msg}",)).start()

        # 2. ניהול שיחה
        if user_id not in chat_sessions:
            chat_sessions[user_id] = model.start_chat(history=[])
            # הנחיה לבוט בכל תחילת שיחה
            chat_sessions[user_id].send_message(
                "אתה העוזר של לינה (LINA Real Estate). ענה בעברית קצרה, נחמדה ומכירתית. נסה להשיג טלפון."
            )
            threading.Thread(target=send_telegram_background, args=(f"🚀 לקוח חדש נכנס!",)).start()

        # 3. תשובה ללקוח
        chat = chat_sessions[user_id]
        response = chat.send_message(user_msg)
        
        return jsonify({'reply': response.text})

    except Exception as e:
        print(f"ERROR: {e}")
        # הודעה מנומסת ללקוח (התיקון בוצע, לא צריך להפחיד אותם)
        return jsonify({'reply': "סליחה, אני מתחבר מחדש למערכת. נסה שוב בעוד רגע או התקשר ללינה."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
