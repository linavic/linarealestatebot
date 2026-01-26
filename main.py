import os
import logging
import threading
import asyncio
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# === 1. הגדרות ולוגים ===
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app) # פותח גישה לאתר

# מפתחות (נלקחים מ-Render)
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GENAI_API_KEY = os.environ.get("GEMINI_API_KEY")
ADMIN_ID = os.environ.get("ADMIN_ID")

# הגדרת Gemini
model = None
if GENAI_API_KEY:
    genai.configure(api_key=GENAI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction="אתה העוזר האישי של לינה סוחוביצקי (LINA Real Estate). תפקידך לענות באדיבות, בעברית, ולנסות לקבל שם וטלפון מהלקוח."
    )

# זיכרון לשיחות באתר
web_chat_sessions = {}

# === 2. פונקציות עזר ===
def notify_lina(text):
    """שולח הודעה ללינה בטלגרם כשיש פעילות באתר"""
    if not TELEGRAM_TOKEN or not ADMIN_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": ADMIN_ID, "text": f"🌐 *אתר:* {text}", "parse_mode": "Markdown"})
    except: pass

# === 3. השרת של האתר (Flask) ===
@app.route('/')
def index():
    return "Lina Bot is Running Correctly!"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    try:
        data = request.json
        user_msg = data.get('message')
        user_id = data.get('user_id', 'guest')

        # זיהוי שיחה חדשה
        if user_id not in web_chat_sessions:
            web_chat_sessions[user_id] = model.start_chat(history=[])
            notify_lina(f"לקוח חדש באתר! ID: {user_id}")

        # שליחת התראה ללינה על הודעת הלקוח
        notify_lina(f"👤 לקוח: {user_msg}")

        # קבלת תשובה מ-Gemini
        chat = web_chat_sessions[user_id]
        response = chat.send_message(user_msg)
        bot_reply = response.text

        # זיהוי ליד (טלפון)
        if any(char.isdigit() for char in user_msg) and len(user_msg) > 6:
            notify_lina(f"🔥 **ליד חם! זוהה טלפון:**\n{user_msg}")

        return jsonify({'reply': bot_reply})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'reply': "תקלה רגעית, אנא נסה שוב."})

def run_flask():
    """מריץ את השרת ברקע"""
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

# === 4. הבוט של טלגרם ===
async def telegram_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """עונה ללקוחות שפונים ישירות בטלגרם"""
    try:
        user_text = update.message.text
        # שימוש באותו מודל חכם גם לטלגרם
        response = model.generate_content(user_text)
        await update.message.reply_text(response.text)
    except:
        await update.message.reply_text("סליחה, אני לא זמין כרגע.")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("היי! אני הבוט של לינה. איך אפשר לעזור?")

# === 5. ההרצה הראשית (מונע התנגשויות) ===
if __name__ == "__main__":
    # א. הפעלת שרת האתר ב-Thread נפרד (לא חוסם)
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print("✅ Website Server Started")

    # ב. הפעלת בוט הטלגרם (תהליך ראשי)
    if TELEGRAM_TOKEN:
        print("✅ Starting Telegram Bot...")
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram_reply))
        
        # הרצה שקטה
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    else:
        print("⚠️ No Telegram Token. Running only Web Server.")
        flask_thread.join()
