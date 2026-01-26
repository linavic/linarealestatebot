import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import requests  # ספרייה לשליחת הודעות

# === הגדרות ===
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
CORS(app)

# === מפתחות ===
GENAI_API_KEY = os.environ.get("GEMINI_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_ID = os.environ.get("ADMIN_ID") # המזהה של לינה

# === הגדרת המוח (AI) ===
model = None
if GENAI_API_KEY:
    genai.configure(api_key=GENAI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction="""
        אתה העוזר האישי של לינה סוחוביצקי (LINA Real Estate).
        תפקידך באתר: לענות ללקוחות באדיבות, בעברית, ולנסות לקבל מספר טלפון.
        """
    )

# === פונקציית הדיווח לטלגרם (החלק החשוב) ===
def notify_lina(text):
    """שולח הודעה ללינה בטלגרם בלי להפעיל בוט מלא"""
    if not TELEGRAM_TOKEN or not ADMIN_ID:
        print("⚠️ חסרים פרטי טלגרם בהגדרות")
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": ADMIN_ID,
            "text": text,
            "parse_mode": "Markdown"
        }
        # שליחה חד-פעמית בלי לחכות לתשובה (Fire and Forget)
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"❌ נכשל בשליחת הודעה לטלגרם: {e}")

# זיכרון שיחות
chat_sessions = {}

@app.route('/')
def home():
    return "Lina Bot + Notifications Active! 🚀"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    if not model:
        return jsonify({'reply': "הבוט מתחבר למוח... נסה שוב עוד רגע."})

    try:
        data = request.json
        user_msg = data.get('message')
        user_id = data.get('user_id', 'guest')

        # 1. זיהוי שיחה חדשה ודיווח ללינה
        if user_id not in chat_sessions:
            chat_sessions[user_id] = model.start_chat(history=[])
            notify_lina(f"🚀 **לקוח חדש באתר!**\nID: {user_id}")

        # 2. דיווח ללינה על תוכן ההודעה
        print(f"User: {user_msg}")
        notify_lina(f"👤 *לקוח:* {user_msg}")

        # 3. זיהוי ליד חם (מספר טלפון)
        if any(char.isdigit() for char in user_msg) and len(user_msg) > 6:
            notify_lina(f"🔥 **שימי לב! הושאר מספר טלפון:**\n{user_msg}")

        # 4. קבלת תשובה מה-AI
        chat = chat_sessions[user_id]
        response = chat.send_message(user_msg)
        
        return jsonify({'reply': response.text})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'reply': "סליחה, יש הפרעה קטנה. נסה שוב."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

