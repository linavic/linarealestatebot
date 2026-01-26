import os
import logging
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import requests

# לוגים ברורים
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app)

# קריאת מפתחות
GENAI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")

# חיבור למוח (Gemini)
model = None
if GENAI_API_KEY:
    try:
        genai.configure(api_key=GENAI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash", 
            system_instruction="אתה העוזר של לינה (LINA Real Estate). ענה בעברית קצרה, נחמדה ומכירתית. נסה להשיג טלפון."
        )
        print("✅ Gemini Connected")
    except Exception as e:
        print(f"❌ Gemini Error: {e}")

chat_sessions = {}

# --- פונקציה פשוטה לשליחת הודעה (בלי בוט) ---
def notify_lina(text):
    if not TELEGRAM_TOKEN or not ADMIN_ID: return
    try:
        # שליחה פשוטה כמו כניסה לאתר אינטרנט
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": ADMIN_ID, "text": text}, timeout=5)
    except:
        pass # אם לא הצליח לשלוח ללינה, לא נורא - העיקר שהאתר לא יקרוס

@app.route('/')
def home():
    return "Lina Website Bot is Active! 🚀"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    if not model:
        return jsonify({'reply': "שגיאת שרת: חסר מפתח AI."})

    try:
        data = request.json
        user_msg = data.get('message')
        user_id = data.get('user_id', 'guest')
        
        print(f"📩 הודעה: {user_msg}")

        # 1. שליחת התראה ללינה (ברקע)
        threading.Thread(target=notify_lina, args=(f"👤 *לקוח באתר:* {user_msg}",)).start()

        # 2. פתיחת שיחה
        if user_id not in chat_sessions:
            chat_sessions[user_id] = model.start_chat(history=[])
            # התראה על לקוח חדש
            threading.Thread(target=notify_lina, args=(f"🚀 **לקוח חדש נכנס!**",)).start()

        # 3. תשובה מה-AI
        chat = chat_sessions[user_id]
        response = chat.send_message(user_msg)
        
        return jsonify({'reply': response.text})

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'reply': "סליחה, יש לי תקלה רגעית. נסה שוב."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
