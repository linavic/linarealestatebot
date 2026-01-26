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

# ניקוי מפתחות (מונע שגיאות העתקה)
def get_key(name):
    val = os.environ.get(name)
    return val.strip() if val else None

API_KEY = get_key("GEMINI_API_KEY")
TELEGRAM_TOKEN = get_key("TELEGRAM_TOKEN")
ADMIN_ID = get_key("ADMIN_ID")

# === כתובות ישירות לגוגל (עוקף את הספרייה התקועה) ===
URL_FLASH = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
URL_PRO = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={API_KEY}"

# זיכרון שיחות
chat_history = {}

def notify_lina(text):
    if not TELEGRAM_TOKEN or not ADMIN_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": ADMIN_ID, "text": text}, timeout=3)
    except: pass

def ask_google_smart(user_id, message):
    # 1. ניהול היסטוריה
    history = chat_history.get(user_id, [])
    history.append({"role": "user", "parts": [{"text": message}]})
    
    # 2. בניית הבקשה
    payload = {
        "contents": history,
        "systemInstruction": {
            "parts": [{"text": "אתה העוזר של לינה (LINA Real Estate). ענה בעברית קצרה ומכירתית. נסה להשיג טלפון."}]
        }
    }

    try:
        # 3. ניסיון ראשון: FLASH (המהיר)
        # print("Trying Flash...")
        response = requests.post(URL_FLASH, json=payload, headers={'Content-Type': 'application/json'}, timeout=10)
        
        # 4. אם נכשל (למשל שגיאת 404) -> עובר מיד ל-PRO
        if response.status_code != 200:
            print(f"Flash failed ({response.status_code}), Switching to PRO...")
            response = requests.post(URL_PRO, json=payload, headers={'Content-Type': 'application/json'}, timeout=10)

        # 5. עיבוד התשובה (בין אם הגיעה מ-Flash או מ-Pro)
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and result['candidates']:
                bot_text = result['candidates'][0]['content']['parts'][0]['text']
                # שמירה בהיסטוריה
                history.append({"role": "model", "parts": [{"text": bot_text}]})
                chat_history[user_id] = history[-10:] 
                return bot_text
        
        # אם גם השני נכשל
        print(f"Final Google Error: {response.text}")
        return "סליחה, יש לי תקלה בחיבור למוח."

    except Exception as e:
        print(f"Network Error: {e}")
        return "תקלה בחיבור לרשת."

# === השרת ===
@app.route('/')
def home():
    return "Lina Smart Bot Active 🚀"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    try:
        if not API_KEY: return jsonify({'reply': "שגיאה: חסר מפתח API."})

        data = request.json
        msg = data.get('message')
        uid = data.get('user_id', 'guest')

        # התראות רקע
        threading.Thread(target=notify_lina, args=(f"👤 *לקוח:* {msg}",)).start()
        if uid not in chat_history:
             threading.Thread(target=notify_lina, args=(f"🚀 לקוח חדש!",)).start()
        if any(char.isdigit() for char in msg) and len(msg) > 6:
            threading.Thread(target=notify_lina, args=(f"🔥 **ליד חם! טלפון:**\n{msg}",)).start()

        # קבלת תשובה (עם המנגנון החכם)
        reply = ask_google_smart(uid, msg)
        
        return jsonify({'reply': reply})

    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({'reply': "תקלה טכנית."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
