import os
import re
import requests
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

def get_env(name):
    val = os.environ.get(name)
    if not val: return None
    return val.strip()

# משתנים
OPENROUTER_API_KEY = get_env("OPENROUTER_API_KEY")
TELEGRAM_TOKEN = get_env("TELEGRAM_TOKEN")
ADMIN_ID = get_env("ADMIN_ID")

# === התיקון החשוב: השם בדיוק כמו באפליקציה שלך ===
NTFY_TOPIC = "linarealestate_bot" 

# הגדרות OpenRouter
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "google/gemini-2.0-flash-001"

# === פונקציית שליחה (גם לטלגרם וגם לאפליקציה בטלפון) ===
def send_alert(message, is_urgent=False):
    # 1. שליחה לטלגרם (גיבוי)
    if TELEGRAM_TOKEN and ADMIN_ID:
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                          json={"chat_id": ADMIN_ID, "text": message, "parse_mode": "HTML"}, timeout=3)
        except: pass

    # 2. שליחה לאפליקציית NTFY (לתוך הטלפון שלך)
    try:
        priority = "high" if is_urgent else "default"
        tags = "rotating_light" if is_urgent else "speech_balloon"
        
        # שליחה לכתובת המדויקת מהצילום מסך שלך
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.replace("<b>", "").replace("</b>", ""), 
            headers={
                "Title": "LinaBot Update",
                "Priority": priority,
                "Tags": tags
            },
            timeout=5
        )
        logger.info(f"Notification sent to ntfy topic: {NTFY_TOPIC}")
    except Exception as e:
        logger.error(f"Ntfy error: {e}")

@app.route('/')
def home():
    return "Lina Bot + NTFY Active 🚀", 200

@app.route('/web-chat', methods=['POST'])
def web_chat():
    if not OPENROUTER_API_KEY:
        return jsonify({'reply': "Error: Missing API Key"}), 500

    try:
        data = request.json
        msg = data.get('message', '').strip()
    except:
        return jsonify({'reply': ""}), 400

    if not msg: return jsonify({'reply': "היי 👋"}), 200

    # === 1. זיהוי טלפון ===
    clean_msg = re.sub(r'\D', '', msg) 
    
    if 9 <= len(clean_msg) <= 13:
        # הודעה דחופה לטלפון שלך!
        alert_text = f"🔥 ליד חם נכנס!\nטלפון: {msg}"
        send_alert(alert_text, is_urgent=True)
        
        return jsonify({'reply': "תודה רבה! המספר התקבל בהצלחה. לינה תחזור אליך בהקדם. 😊"}), 200
    
    # סתם שיחה - התראה שקטה
    send_alert(f"לקוח כותב: {msg}", is_urgent=False)

    # === 2. שליחה ל-OpenRouter ===
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://linarealestate.net", 
        "X-Title": "LinaBot"
    }

    system_prompt = """
    You are Lina's warm and professional real estate assistant.
    INSTRUCTIONS:
    1. Detect language and reply in the SAME language.
    2. Be friendly and engaging.
    3. Goal: Get Name and Phone Number.
    4. NO internal thoughts.
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
            reply = result['choices'][0]['message']['content']
            reply = re.sub(r'thought_.*?(\n|$)', '', reply, flags=re.IGNORECASE).strip()
            return jsonify({'reply': reply}), 200
        else:
            return jsonify({'reply': "אשמח לעזור! אנא השאר פרטים."}), 200

    except:
        return jsonify({'reply': "אשמח לעזור! אנא השאר פרטים."}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
