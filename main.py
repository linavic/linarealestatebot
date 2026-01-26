import os
import logging
import threading
import time
import asyncio
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import requests
from telegram import Update
from telegram.error import Conflict
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# === הגדרת לוגים (כדי שנראה מה קורה ב-Render) ===
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# === מפתחות ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GENAI_API_KEY = os.environ.get("GEMINI_API_KEY")
ADMIN_ID = os.environ.get("ADMIN_ID")

# === הגדרת Gemini ===
model = None
if GENAI_API_KEY:
    try:
        genai.configure(api_key=GENAI_API_KEY)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction="אתה העוזר האישי של לינה סוחוביצקי (LINA Real Estate). תפקידך לענות באדיבות, בעברית, ולנסות לקבל שם וטלפון מהלקוח."
        )
        print("✅ Gemini AI Connected Successfully")
    except Exception as e:
        print(f"❌ Error connecting to Gemini: {e}")
else:
    print("⚠️ Warning: GEMINI_API_KEY is missing")

# זיכרון לשיחות באתר
web_chat_sessions = {}

# === פונקציות עזר ===
def notify_lina(text):
    """שולח הודעה ללינה בטלגרם"""
    if not TELEGRAM_TOKEN or not ADMIN_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": ADMIN_ID, "text": f"🌐 *אתר:* {text}", "parse_mode": "Markdown"})
    except Exception as e:
        print(f"Failed to notify Lina: {e}")

# === שרת האתר (Flask) ===
@app.route('/')
def index():
    return "Lina Bot Server is Running and Healthy!"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    if not model:
        return jsonify({'reply': "שגיאת שרת: המוח (AI) לא מחובר."})

    try:
        data = request.json
        user_msg = data.get('message')
        user_id = data.get('user_id', 'guest')

        # זיהוי שיחה חדשה
        if user_id not in web_chat_sessions:
            web_chat_sessions[user_id] = model.start_chat(history=[])
            notify_lina(f"לקוח חדש באתר! ID: {user_id}")

        print(f"📩 Web Message from {user_id}: {user_msg}") # לוג לשרת
        notify_lina(f"👤 לקוח: {user_msg}")

        # שליחה ל-AI
        chat = web_chat_sessions[user_id]
        response = chat.send_message(user_msg)
        print(f"🤖 AI Reply: {response.text}") # לוג לשרת

        # בדיקת ליד
        if any(char.isdigit() for char in user_msg) and len(user_msg) > 6:
            notify_lina(f"🔥 **ליד חם! זוהה טלפון:**\n{user_msg}")

        return jsonify({'reply': response.text})

    except Exception as e:
        print(f"❌ Web Chat Error: {e}")
        return jsonify({'reply': "תקלה רגעית, אנא נסה שוב."})

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

# === בוט טלגרם ===
async def telegram_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not model:
        await update.message.reply_text("הבוט בשיפוצים (אין חיבור ל-AI).")
        return

    try:
        user_text = update.message.text
        print(f"📩 Telegram Message: {user_text}") # לוג
        response = model.generate_content(user_text)
        await update.message.reply_text(response.text)
    except Exception as e:
        print(f"❌ Telegram AI Error: {e}")
        await update.message.reply_text("סליחה, יש לי תקלה רגעית.")

def run_telegram_loop():
    """מריץ את הטלגרם בלולאה חכמה שמונעת קריסות"""
    if not TELEGRAM_TOKEN:
        print("⚠️ No Telegram Token - Bot disabled.")
        return

    asyncio.set_event_loop(asyncio.new_event_loop())
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_reply))
    application.add_handler(CommandHandler("start", lambda u,c: u.message.reply_text("היי! אני העוזר של לינה.")))

    print("🚀 Starting Telegram Polling...")
    
    # מנגנון ה-Anti-Crash
    while True:
        try:
            application.run_polling(allowed_updates=Update.ALL_TYPES, close_loop=False)
        except Conflict:
            print("⚠️ Conflict Error: Another bot is running. Waiting 5 seconds...")
            time.sleep(5) # מחכה שהבוט השני ימות ומנסה שוב
        except Exception as e:
            print(f"❌ Critical Telegram Error: {e}. Restarting in 5s...")
            time.sleep(5)

# === הפעלה ===
if __name__ == "__main__":
    # 1. הרצת טלגרם ברקע
    t = threading.Thread(target=run_telegram_loop, daemon=True)
    t.start()

    # 2. הרצת האתר
    run_flask()
