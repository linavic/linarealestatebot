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

# משתמשים במודל FLASH שעבד לך מקודם
GOOGLE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"

chat_history = {}

# === שליחה לטלגרם ===
def notify_lina(text):
    if not TELEGRAM_TOKEN or not ADMIN_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": ADMIN_ID, "text": text}, timeout=3)
    except: pass

# === המוח של הבוט ===
def ask_google(user_id, message):
    history = chat_history.get(user_id, [])
    history.append({"role": "user", "parts": [{"text": message}]})
    
    # הוראה קשוחה לבוט: בלי מחשבות, בלי אופציות
    system_instruction = """
    You are Lina Real Estate's assistant.
    RULES:
    1. Reply ONLY in the language the user speaks.
    2. Be short, polite, and sales-oriented.
    3. YOUR GOAL: Get the Name and Phone Number.
    4. CRITICAL: NEVER output 'thought_', 'Option 1', or internal reasoning. Just the final reply.
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
                
                # === מספריים: חיתוך שטויות אם הן מופיעות ===
                # אם הבוט מתחיל לחפור עם thought_ או Option, אנחנו מוחקים את זה ידנית
                if "thought_" in bot_text or "**Option" in bot_text:
                    # במקום השטויות, נחזיר תשובה בטוחה
                    bot_text = "אשמח לעזור לך! כדי שנוכל להתקדם, מה שמך ומספר הטלפון שלך?"
                
                # שמירה בהיסטוריה
                history.append({"role": "model", "parts": [{"text": bot_text}]})
                chat_history[user_id] = history[-10:]
                return bot_text
        
        # אם גוגל לא ענה טוב
        return "אשמח לעזור, אנא השאר פרטים (שם וטלפון) ואחזור אליך."

    except Exception as e:
        print(f"Error: {e}")
        return "תקלה בחיבור. נסה שוב."

@app.route('/')
def home():
    return "Lina Bot Fixed & Clean 🚀"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    try:
        if not API_KEY: return jsonify({'reply': "Error: API Key Missing"})

        data = request.json
        msg = data.get('message', '')
        uid = data.get('user_id', 'guest')

        # === זיהוי ליד ושליחה לטלגרם ===
        # מחפש רצף של 9-10 ספרות
        phone_match = re.search(r'\d{9,10}', msg.replace('-', '').replace(' ', ''))
        
        if phone_match:
            # מצאנו טלפון! שולח לך הודעה דחופה
            notify_lina(f"✅ **יש ליד חדש!**\nהלקוח כתב: {msg}")
        else:
            # סתם שיחה - מעדכן אותך ברקע
            threading.Thread(target=notify_lina, args=(f"💬 {msg}",)).start()

        # קבלת תשובה
        reply = ask_google(uid, msg)
        return jsonify({'reply': reply})

    except Exception as e:
        return jsonify({'reply': "Error"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
