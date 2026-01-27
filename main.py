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

# קריאת משתנים
def get_env(name):
    val = os.environ.get(name)
    return val.strip() if val else None

# קוראים את המפתח החדש שהגדרת ב-Render
OPENROUTER_API_KEY = get_env("OPENROUTER_API_KEY")
TELEGRAM_TOKEN = get_env("TELEGRAM_TOKEN")
ADMIN_ID = get_env("ADMIN_ID")

# הגדרות OpenRouter
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# נשתמש במודל Gemini 2.0 Flash המהיר והחכם דרך OpenRouter
MODEL_NAME = "google/gemini-2.0-flash-001"

def notify_lina(text):
    if not TELEGRAM_TOKEN or not ADMIN_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": ADMIN_ID, "text": text, "parse_mode": "HTML"}, timeout=3)
    except: pass

@app.route('/')
def home():
    return "Lina OpenRouter Bot Active 🚀", 200

@app.route('/web-chat', methods=['POST'])
def web_chat():
    # בדיקה שיש מפתח
    if not OPENROUTER_API_KEY:
        return jsonify({'reply': "Error: Missing OpenRouter API Key"}), 500

    try:
        data = request.json
        msg = data.get('message', '').strip()
    except:
        return jsonify({'reply': ""}), 400

    if not msg: return jsonify({'reply': "היי 👋"}), 200

    # === 1. זיהוי טלפון (קודם כל ולפני הכל) ===
    clean_msg = msg.replace('-', '').replace(' ', '')
    if re.search(r'\d{9,10}', clean_msg):
        notify_lina(f"🔥 <b>ליד חם! הושאר טלפון:</b>\n{msg}")
        return jsonify({'reply': "תודה רבה! קיבלתי את המספר, לינה תחזור אליך בהקדם. 😊"}), 200
    
    # סתם שיחה - עדכון שקט
    notify_lina(f"💬 <b>הודעה באתר:</b>\n{msg}")

    # === 2. שליחה ל-OpenRouter ===
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://linarealestate.net", 
        "X-Title": "LinaBot"
    }

    # ההוראות לבוט
    system_prompt = """
    You are Lina's real estate assistant.
    INSTRUCTIONS:
    1. Reply in the SAME language as the user (Hebrew/Russian/English).
    2. Be short, polite, and professional.
    3. Goal: Ask for their Name and Phone Number.
    4. NO internal thoughts ("thought" / "analysis"). Just the final reply.
    """

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": msg}
        ]
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            # חילוץ התשובה (פורמט OpenAI סטנדרטי)
            reply = result['choices'][0]['message']['content']
            
            # ניקוי רעשים ליתר ביטחון
            reply = re.sub(r'thought_.*?(\n|$)', '', reply, flags=re.IGNORECASE).strip()
            
            return jsonify({'reply': reply}), 200
        else:
            # במקרה של שגיאה
            print(f"OpenRouter Error: {response.text}")
            return jsonify({'reply': "אשמח לעזור! אנא השאר פרטים ואחזור אליך."}), 200

    except Exception as e:
        print(f"Connection Error: {e}")
        return jsonify({'reply': "אשמח לעזור! אנא השאר שם וטלפון."}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
