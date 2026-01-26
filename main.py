import os
import logging
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

# === הגדרות ===
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
CORS(app)

# מפתחות
API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID")

# כתובת ישירה לגוגל (עוקף ספריות)
GOOGLE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"

# זיכרון שיחות פשוט
chat_history = {}

# === פונקציות עזר ===
def notify_lina(text):
    """שולח הודעה ללינה בטלגרם"""
    if not TELEGRAM_TOKEN or not ADMIN_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": ADMIN_ID, "text": text}, timeout=4)
    except: pass

def ask_google_direct(user_id, message):
    """שולח הודעה לגוגל ישירות בלי ספרייה"""
    # שליפת היסטוריה
    history = chat_history.get(user_id, [])
    
    # הוספת ההודעה החדשה
    history.append({"role": "user", "parts": [{"text": message}]})
    
    # הכנת הגוף לבקשה
    payload = {
        "contents": history,
        "systemInstruction": {
            "parts": [{"text": "אתה העוזר של לינה (LINA Real Estate). ענה בעברית קצרה, נחמדה ומכירתית. נסה להשיג טלפון."}]
        }
    }

    # שליחה לגוגל
    response = requests.post(GOOGLE_URL, json=payload, headers={'Content-Type': 'application/json'})
    
    if response.status_code == 200:
        result = response.json()
        bot_text = result['candidates'][0]['content']['parts'][0]['text']
        
        # שמירת התשובה בהיסטוריה
        history.append({"role": "model", "parts": [{"text": bot_text}]})
        chat_history[user_id] = history[-10:] # שומר רק 10 הודעות אחרונות
        
        return bot_text
    else:
        print(f"Google Error: {response.text}")
        return "סליחה, יש לי תקלה רגעית בחיבור."

# === השרת ===
@app.route('/')
def home():
    return "Lina Direct Bot Active! 🚀"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    try:
        if not API_KEY: 
            return jsonify({'reply': "שגיאה: חסר מפתח גוגל בשרת."})

        data = request.json
        msg = data.get('message')
        uid = data.get('user_id', 'guest')

        # 1. דיווח ללינה
        threading.Thread(target=notify_lina, args=(f"👤 *לקוח:* {msg}",)).start()

        # 2. אם לקוח חדש
        if uid not in chat_history:
             threading.Thread(target=notify_lina, args=(f"🚀 לקוח חדש נכנס!",)).start()

        # 3. תשובה מגוגל (ישיר)
        reply = ask_google_direct(uid, msg)
        
        return jsonify({'reply': reply})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'reply': "תקלה טכנית."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
