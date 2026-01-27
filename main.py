import os
import re
import requests
import logging
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
CORS(app)

def get_key(name):
    val = os.environ.get(name)
    return val.strip() if val else None

API_KEY = get_key("GEMINI_API_KEY")
TELEGRAM_TOKEN = get_key("TELEGRAM_TOKEN")
ADMIN_ID = get_key("ADMIN_ID")

# כתובת למודל שעבד בוידאו (Flash)
URL_FLASH = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={API_KEY}"
# כתובת גיבוי (Pro) למקרה חירום
URL_PRO = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={API_KEY}"

def notify_lina(text):
    if not TELEGRAM_TOKEN or not ADMIN_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": ADMIN_ID, "text": text}, timeout=3)
    except: pass

def ask_google(prompt_text):
    payload = {"contents": [{"parts": [{"text": prompt_text}]}]}
    
    # נסיון 1: המודל המהיר (שעבד בוידאו)
    try:
        response = requests.post(URL_FLASH, json=payload, headers={'Content-Type': 'application/json'}, timeout=8)
        if response.status_code == 200: return response
    except: pass

    # נסיון 2: מודל גיבוי
    try:
        response = requests.post(URL_PRO, json=payload, headers={'Content-Type': 'application/json'}, timeout=8)
        return response
    except: return None

@app.route('/')
def home():
    return "Lina Bot - Video Version Fixed 🚀", 200

@app.route('/web-chat', methods=['POST'])
def web_chat():
    if not API_KEY: return jsonify({'reply': "Error: API Key Missing"})

    try:
        data = request.json
        msg = data.get('message', '')
        
        # 1. אם יש טלפון - חותכים מיד! (לא שואלים את גוגל)
        clean_msg = msg.replace('-', '').replace(' ', '')
        if re.search(r'\d{9,10}', clean_msg):
            notify_lina(f"🔥 **ליד חם! הושאר טלפון:**\n{msg}")
            return jsonify({'reply': "תודה רבה! קיבלתי את המספר, לינה תחזור אליך בהקדם. 😊"})
        
        # סתם הודעה - מעדכן אותך בשקט
        threading.Thread(target=notify_lina, args=(f"💬 {msg}",)).start()

        # 2. הכנת ההוראה לבוט (בתוך ההודעה כדי למנוע באגים)
        full_prompt = f"""
        You are Lina's real estate assistant.
        User said: "{msg}"
        
        INSTRUCTIONS:
        1. Reply in the SAME language as the user.
        2. Be short, polite, and sales-oriented.
        3. Goal: Ask for their Name and Phone Number.
        4. CRITICAL: Do NOT show internal thoughts (thought_...). Just the final reply.
        """

        # 3. שליחה לגוגל
        response = ask_google(full_prompt)
        
        if response and response.status_code == 200:
            result = response.json()
            if 'candidates' in result and result['candidates']:
                bot_text = result['candidates'][0]['content']['parts'][0]['text']
                
                # === המספריים (התיקון לבעיה מהוידאו) ===
                # מוחק כל מה שכתוב באנגלית טכנית או מחשבות
                bot_text = re.sub(r'thought_[\s\S]*?(?=\n|$)', '', bot_text) # מוחק thought_
                bot_text = bot_text.replace("Analysis:", "").replace("Option 1:", "")
                bot_text = bot_text.strip()
                
                # אם בטעות הוא מחק הכל ונשאר ריק
                if not bot_text or len(bot_text) < 2:
                    return jsonify({'reply': "אשמח לעזור! מה שמך ומספר הטלפון שלך?"})

                return jsonify({'reply': bot_text})

        # אם גוגל נכשל
        return jsonify({'reply': "אשמח לעזור! אנא השאר שם וטלפון ואחזור אליך."})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'reply': "אשמח לעזור! אנא השאר פרטים ליצירת קשר."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
