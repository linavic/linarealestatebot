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

# כתובות ישירות לגוגל (עוקף ספריות)
URL_FLASH = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
URL_PRO = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={API_KEY}"

# זיכרון שיחות
chat_history = {}

# === פונקציית דיווח לטלגרם ===
def notify_lina(text):
    """שולח הודעה ללינה בטלגרם"""
    if not TELEGRAM_TOKEN or not ADMIN_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": ADMIN_ID, "text": text, "parse_mode": "Markdown"}, timeout=4)
    except: pass

# === הפונקציה החכמה שפונה לגוגל ===
def ask_google(user_id, message):
    # 1. הכנת ההיסטוריה
    history = chat_history.get(user_id, [])
    history.append({"role": "user", "parts": [{"text": message}]})
    
    # 2. הגדרת ה"אישיות" של הבוט
    payload = {
        "contents": history,
        "systemInstruction": {
            "parts": [{"text": "אתה העוזר האישי של לינה (LINA Real Estate). ענה בעברית קצרה, נחמדה ומכירתית. נסה להשיג טלפון מהלקוח."}]
        }
    }

    # 3. ניסיון ראשון: מודל FLASH המהיר
    try:
        response = requests.post(URL_FLASH, json=payload, headers={'Content-Type': 'application/json'}, timeout=10)
        
        # אם נכשל (כמו שקרה לך), עובר אוטומטית לתוכנית ב'
        if response.status_code != 200:
            print(f"Flash failed ({response.status_code}), switching to Pro...")
            response = requests.post(URL_PRO, json=payload, headers={'Content-Type': 'application/json'}, timeout=10)

        # 4. עיבוד התשובה
        if response.status_code == 200:
            result = response.json()
            bot_text = result['candidates'][0]['content']['parts'][0]['text']
            
            # שמירה בזיכרון
            history.append({"role": "model", "parts": [{"text": bot_text}]})
            chat_history[user_id] = history[-20:] # שומר 20 הודעות אחרונות
            return bot_text
        else:
            print(f"Google Error: {response.text}")
            return "סליחה, אני לא מצליח להתחבר כרגע. אנא נסה שוב."

    except Exception as e:
        print(f"Connection Error: {e}")
        return "תקלה בחיבור לרשת."

# === השרת ===
@app.route('/')
def home():
    return "Lina Bot (Direct API) is Active! 🚀"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    try:
        # בדיקה בסיסית
        if not API_KEY: return jsonify({'reply': "שגיאה: חסר מפתח API בשרת."})

        data = request.json
        msg = data.get('message')
        uid = data.get('user_id', 'guest')

        # 1. דיווח ללינה (רץ ברקע כדי לא לתקוע)
        threading.Thread(target=notify_lina, args=(f"👤 *לקוח:* {msg}",)).start()

        # 2. זיהוי לקוח חדש
        if uid not in chat_history:
             threading.Thread(target=notify_lina, args=(f"🚀 **לקוח חדש נכנס לאתר!**",)).start()

        # 3. זיהוי טלפון (ליד)
        if any(char.isdigit() for char in msg) and len(msg) > 6:
            threading.Thread(target=notify_lina, args=(f"🔥 **ליד חם! הושאר טלפון:**\n{msg}",)).start()

        # 4. קבלת תשובה
        reply = ask_google(uid, msg)
        
        return jsonify({'reply': reply})

    except Exception as e:
        print(f"Server Error: {e}")
        return jsonify({'reply': "תקלה טכנית בשרת."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
