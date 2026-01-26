import os
import logging
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import requests

# === הגדרות לוגים (כדי שנראה שגיאות ב-Render) ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# === קבלת מפתחות מ-Render (עם ניקוי רווחים) ===
def get_env(key):
    val = os.environ.get(key)
    return val.strip() if val else None

GENAI_API_KEY = get_env("GEMINI_API_KEY")
TELEGRAM_TOKEN = get_env("TELEGRAM_TOKEN")
ADMIN_ID = get_env("ADMIN_ID")

# === חיבור למוח (Gemini) ===
model = None
if GENAI_API_KEY:
    try:
        genai.configure(api_key=GENAI_API_KEY)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction="""
            אתה העוזר האישי של לינה סוחוביצקי (LINA Real Estate).
            תפקידך באתר: לענות ללקוחות, להיות נחמד ומקצועי.
            נסה לקבל מהם מספר טלפון לחזרה.
            ענה בעברית קצרה.
            """
        )
        print("✅ Gemini connected successfully")
    except Exception as e:
        print(f"❌ Error connecting to Gemini: {e}")
else:
    print("⚠️ Critical: GEMINI_API_KEY is missing!")

# זיכרון שיחות
chat_sessions = {}

# === פונקציית דיווח לטלגרם (רץ ברקע) ===
def send_telegram_background(text):
    """שולח הודעה ללינה בלי לתקוע את האתר"""
    if not TELEGRAM_TOKEN or not ADMIN_ID:
        print("⚠️ Telegram keys missing, skipping notification.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": ADMIN_ID,
            "text": text,
            "parse_mode": "Markdown"
        }
        # שליחה עם timeout קצר כדי לא להיתקע
        requests.post(url, json=payload, timeout=5)
        print(f"📢 Notification sent to Lina: {text[:20]}...")
    except Exception as e:
        print(f"⚠️ Failed to send Telegram: {e}")

def notify_lina(text):
    # מפעיל את השליחה בשרשור נפרד (Thread) כדי לא לעכב את התשובה ללקוח
    threading.Thread(target=send_telegram_background, args=(text,)).start()

# === השרת ===
@app.route('/')
def home():
    return "Lina Bot is Running! 🚀"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    # בדיקה שהמוח מחובר
    if not model:
        return jsonify({'reply': "שגיאת מערכת: הבוט לא מחובר ל-AI."})

    try:
        data = request.json
        user_msg = data.get('message')
        user_id = data.get('user_id', 'guest')

        print(f"📩 הודעה מ-{user_id}: {user_msg}")

        # 1. יצירת שיחה
        if user_id not in chat_sessions:
            chat_sessions[user_id] = model.start_chat(history=[])
            notify_lina(f"🚀 **לקוח חדש באתר!**\nID: {user_id}")

        # 2. דיווח ללינה על תוכן ההודעה (ברקע)
        notify_lina(f"👤 *לקוח:* {user_msg}")

        # 3. בדיקת ליד (מספר טלפון)
        if any(char.isdigit() for char in user_msg) and len(user_msg) > 6:
            notify_lina(f"🔥 **ליד חם! הושאר טלפון:**\n{user_msg}")

        # 4. יצירת תשובה (זה החלק שלוקח זמן)
        chat = chat_sessions[user_id]
        response = chat.send_message(user_msg)
        
        return jsonify({'reply': response.text})

    except Exception as e:
        print(f"❌ Critical Error inside web_chat: {e}")
        # במקרה של שגיאה, מחזירים הודעה ידידותית
        return jsonify({'reply': "סליחה, יש לי תקלה רגעית. אנא נסה שוב או התקשר ללינה."})

if __name__ == "__main__":
    # שימוש בפורט של Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
