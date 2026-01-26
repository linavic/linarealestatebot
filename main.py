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

# קריאת מפתחות
GENAI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")

# חיבור למוח
model = None
if GENAI_API_KEY:
    try:
        genai.configure(api_key=GENAI_API_KEY)
        # חוזרים למודל המהיר והחכם (עכשיו שיש לנו ספרייה מעודכנת)
        model = genai.GenerativeModel("gemini-1.5-flash", 
            system_instruction="אתה העוזר של לינה (LINA Real Estate). ענה בעברית קצרה ומכירתית. נסה להשיג טלפון."
        )
        print("✅ Gemini Connected")
    except Exception as e:
        print(f"❌ Error: {e}")

chat_sessions = {}

def notify_lina(text):
    if TELEGRAM_TOKEN and ADMIN_ID:
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                          json={"chat_id": ADMIN_ID, "text": text}, timeout=4)
        except: pass

@app.route('/')
def home(): return "Lina Bot Updated! 🚀"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    try:
        if not GENAI_API_KEY: return jsonify({'reply': "🔴 שגיאה: חסר מפתח AI"})
        if not model: return jsonify({'reply': "🔴 שגיאה: המודל לא נטען"})

        data = request.json
        msg = data.get('message')
        uid = data.get('user_id', 'guest')

        # דיווח ללינה
        threading.Thread(target=notify_lina, args=(f"👤 *לקוח:* {msg}",)).start()

        # ניהול שיחה
        if uid not in chat_sessions:
            chat_sessions[uid] = model.start_chat(history=[])
            threading.Thread(target=notify_lina, args=(f"🚀 לקוח חדש!",)).start()

        # שליחה ל-AI
        response = chat_sessions[uid].send_message(msg)
        return jsonify({'reply': response.text})

    except Exception as e:
        # במקרה של שגיאה - נראה אותה בצ'אט כדי לתקן
        return jsonify({'reply': f"🔴 שגיאה טכנית:\n{str(e)}"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
