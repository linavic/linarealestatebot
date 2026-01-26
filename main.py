import os
import logging
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
CORS(app)

# קבלת מפתחות
def get_key(name):
    val = os.environ.get(name)
    return val.strip() if val else None

API_KEY = get_key("GEMINI_API_KEY")
TELEGRAM_TOKEN = get_key("TELEGRAM_TOKEN")
ADMIN_ID = get_key("ADMIN_ID")

# === רשימת המודלים לניסיון (מפתח מאסטר) ===
# הבוט ינסה אותם לפי הסדר עד שאחד יעבוד
MODELS_TO_TRY = [
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-1.0-pro",
    "gemini-pro"
]

chat_history = {}

# פונקציית התראה לטלגרם
def notify_lina(text):
    if not TELEGRAM_TOKEN or not ADMIN_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": ADMIN_ID, "text": text}, timeout=3)
    except: pass

# === הפונקציה החכמה שמנסה הכל ===
def ask_google_bulletproof(user_id, message):
    # ניהול היסטוריה
    history = chat_history.get(user_id, [])
    history.append({"role": "user", "parts": [{"text": message}]})
    
    # הוספת הנחיה
    current_prompt = {
        "contents": history,
        "systemInstruction": {
            "parts": [{"text": "אתה העוזר של לינה (LINA Real Estate). ענה בעברית קצרה, נחמדה ומכירתית."}]
        }
    }

    last_error = ""

    # === הלב של הבוט: לולאת הניסיונות ===
    for model_name in MODELS_TO_TRY:
        try:
            # בניית כתובת דינמית לכל מודל
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"
            
            # ניסיון שליחה
            response = requests.post(url, json=current_prompt, headers={'Content-Type': 'application/json'}, timeout=8)
            
            if response.status_code == 200:
                # הצלחה!
                result = response.json()
                if 'candidates' in result and result['candidates']:
                    bot_text = result['candidates'][0]['content']['parts'][0]['text']
                    
                    # שמירה בהיסטוריה
                    history.append({"role": "model", "parts": [{"text": bot_text}]})
                    chat_history[user_id] = history[-10:]
                    
                    # הצלחנו, יוצאים מהלולאה ומחזירים תשובה
                    return bot_text
            else:
                # שגיאה במודל הזה, שומרים אותה וממשיכים לבא בתור
                last_error = f"Model {model_name} failed: {response.text}"
                print(f"⚠️ {model_name} failed, trying next...")
                
        except Exception as e:
            last_error = f"Network error on {model_name}: {str(e)}"

    # אם כל המודלים נכשלו
    print(f"❌ ALL MODELS FAILED. Last Error: {last_error}")
    return f"תקלה בחיבור לגוגל. שגיאה: {last_error}"

# === השרת ===
@app.route('/')
def home():
    return "Lina Master-Bot Active 🚀"

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
            threading.Thread(target=notify_lina, args=(f"🔥 **ליד חם!**\n{msg}",)).start()

        # קבלת תשובה
        reply = ask_google_bulletproof(uid, msg)
        
        return jsonify({'reply': reply})

    except Exception as e:
        return jsonify({'reply': "תקלה טכנית בשרת."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
