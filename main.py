import os
import logging
import threading
import re
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
CORS(app)

# ניקוי מפתחות (מונע תקלות רווחים)
def get_key(name):
    val = os.environ.get(name)
    return val.strip() if val else None

API_KEY = get_key("GEMINI_API_KEY")
TELEGRAM_TOKEN = get_key("TELEGRAM_TOKEN")
ADMIN_ID = get_key("ADMIN_ID")

# כתובת למודל היציב
GOOGLE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"

chat_history = {}

# === שליחת התראה ללינה בטלגרם ===
def notify_lina(text):
    if not TELEGRAM_TOKEN or not ADMIN_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": ADMIN_ID, "text": text}, timeout=3)
    except: pass

def ask_google(user_id, message):
    history = chat_history.get(user_id, [])
    history.append({"role": "user", "parts": [{"text": message}]})
    
    # === ההוראה החדשה: מונעת "מחשבות" ומחייבת הוצאת טלפון ===
    system_instruction = """
    תפקידך: העוזר האישי של לינה (LINA Real Estate).
    מטרה יחידה: לקבל מהלקוח מספר טלפון כדי שלינה תחזור אליו.
    חוקים:
    1. ענה אך ורק בעברית.
    2. היה קצר, ענייני ונחמד.
    3. אל תציג שום טקסט של "מחשבה" או "thought". תן רק את התשובה ללקוח.
    4. בכל תשובה, נסה לכוון לקבלת מספר טלפון. דוגמה: "אשמח לתת פרטים נוספים, מה הנייד שלך?"
    """

    payload = {
        "contents": history,
        "systemInstruction": {
            "parts": [{"text": system_instruction}]
        }
    }

    try:
        response = requests.post(GOOGLE_URL, json=payload, headers={'Content-Type': 'application/json'}, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and result['candidates']:
                bot_text = result['candidates'][0]['content']['parts'][0]['text']
                
                # ניקוי חירום: אם הבוט בכל זאת כתב "thought", נחתוך את זה
                if "thought" in bot_text or "Option" in bot_text:
                    bot_text = "אשמח לעזור! כדי שאהיה מדויק, תוכל להשאיר לי מספר טלפון ואחזור אליך מיד?"

                # שמירה בהיסטוריה
                history.append({"role": "model", "parts": [{"text": bot_text}]})
                chat_history[user_id] = history[-10:]
                return bot_text
        
        print(f"Google Error: {response.text}")
        return "סליחה, אני בודק משהו במערכת. בינתיים, מה המספר שלך?"

    except Exception as e:
        print(f"Net Error: {e}")
        return "תקלה בחיבור. אנא נסה שוב."

@app.route('/')
def home():
    return "Lina Lead-Bot Active 🚀"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    try:
        if not API_KEY: return jsonify({'reply': "שגיאה: חסר מפתח API."})

        data = request.json
        msg = data.get('message')
        uid = data.get('user_id', 'guest')

        # === מנגנון זיהוי לידים ושליחה ללינה ===
        
        # 1. האם יש מספר טלפון בהודעה?
        # מחפש רצף של לפחות 9 ספרות
        phone_match = re.search(r'\d{9,10}', msg.replace('-', ''))
        
        if phone_match:
            # מצאנו טלפון! שליחת התראה דחופה
            threading.Thread(target=notify_lina, args=(f"🔥 **יש ליד חדש!**\nלקוח השאיר טלפון: {msg}",)).start()
        else:
            # סתם הודעה רגילה
            threading.Thread(target=notify_lina, args=(f"👤 הודעה באתר: {msg}",)).start()

        # קבלת תשובה
        reply = ask_google(uid, msg)
        return jsonify({'reply': reply})

    except Exception as e:
        return jsonify({'reply': "תקלה טכנית."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
