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

# קבלת מפתחות
def get_key(name):
    val = os.environ.get(name)
    return val.strip() if val else None

API_KEY = get_key("GEMINI_API_KEY")
TELEGRAM_TOKEN = get_key("TELEGRAM_TOKEN")
ADMIN_ID = get_key("ADMIN_ID")

# כתובת למודל Flash המהיר
GOOGLE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"

chat_history = {}

# === שליחת הודעה לטלגרם של לינה ===
def notify_lina(text):
    if not TELEGRAM_TOKEN or not ADMIN_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": ADMIN_ID, "text": text}, timeout=3)
    except: pass

def ask_google(user_id, message):
    history = chat_history.get(user_id, [])
    history.append({"role": "user", "parts": [{"text": message}]})
    
    # === המוח החדש: כל השפות + בקשת טלפון ===
    system_instruction = """
    You are the AI Assistant of Lina Suhovitsky (LINA Real Estate).
    
    YOUR RULES:
    1. **Language:** Detect the language of the user's message (Hebrew, Russian, French, English, etc.) and reply in the EXACT SAME language.
    2. **Goal:** Your main goal is to get the user's NAME and PHONE NUMBER.
    3. **Strategy:** - Answer the user's question briefly and politely.
       - Immediately after answering, ask for their contact details to continue the service.
       - Example (Hebrew): "אשמח לתת לך פרטים מלאים! מה שמך ומספר הטלפון שלך?"
       - Example (Russian): "Я с радостью расскажу подробнее! Как вас зовут и какой у вас номер телефона?"
       - Example (French): "Je serais ravi de vous donner plus de détails! Quel est votre nom et votre numéro de téléphone ?"
    4. **Forbidden:** Do NOT output internal thoughts or "thought" tags. Only the final reply.
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
                
                # מחיקת "מחשבות" אם הבוט בטעות פלט אותן
                if "thought" in bot_text: 
                    # תשובה גנרית בטוחה במקרה של תקלה בטקסט
                    return "אשמח לעזור! כדי שנוכל להתקדם, מה שמך ומספר הטלפון שלך?"

                # שמירה בהיסטוריה
                history.append({"role": "model", "parts": [{"text": bot_text}]})
                chat_history[user_id] = history[-10:]
                return bot_text
        
        return "System update... Please leave your Name and Phone number."

    except Exception as e:
        print(f"Error: {e}")
        return "Connection error. Please try again."

@app.route('/')
def home():
    return "Lina Multi-Language Bot Active 🌍"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    try:
        if not API_KEY: return jsonify({'reply': "Error: Missing API Key"})

        data = request.json
        msg = data.get('message', '')
        uid = data.get('user_id', 'guest')

        # === זיהוי פרטי קשר ושליחה לטלגרם ===
        
        # 1. בדיקה אם יש מספר טלפון (רצף ספרות)
        phone_match = re.search(r'\d{9,10}', msg.replace('-', '').replace(' ', ''))
        
        if phone_match:
            # שלח ללינה התראה דחופה!
            notify_lina(f"✅ **התקבלו פרטי קשר!**\nהלקוח כתב: {msg}")
        else:
            # סתם עדכון על שיחה
            threading.Thread(target=notify_lina, args=(f"💬 לקוח באתר: {msg}",)).start()

        # קבלת תשובה מהבוט
        reply = ask_google(uid, msg)
        return jsonify({'reply': reply})

    except Exception as e:
        return jsonify({'reply': "Error"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
