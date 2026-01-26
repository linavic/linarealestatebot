import os
import logging
import asyncio
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# === הגדרות לוגים (כדי למנוע עומס) ===
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# === הגדרות מפתחות ===
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GENAI_API_KEY = os.environ.get("GEMINI_API_KEY")
ADMIN_ID = os.environ.get("ADMIN_ID") # המזהה של לינה בטלגרם

# === הגדרת Gemini AI ===
if GENAI_API_KEY:
    genai.configure(api_key=GENAI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction="""
        אתה העוזר האישי החכם של לינה סוחוביצקי (LINA Real Estate).
        תפקידך: לענות ללקוחות, להיות נחמד, שיווקי ולנסות להשיג לידים (שם וטלפון).
        הנחיות חשובות:
        1. ענה בעברית טבעית וקצרה.
        2. המטרה שלך היא לגרום ללקוח להשאיר טלפון או להתקשר ללינה.
        3. הטלפון של לינה: 054-4326270.
        """
    )
else:
    model = None
    print("Warning: Gemini API Key missing!")

chat_sessions = {}

# === שרת Flask (עבור האתר) ===
app = Flask(__name__)
CORS(app)

def notify_lina_telegram(text):
    """שולח התראה ללינה בטלגרם על פעילות באתר"""
    if not TELEGRAM_TOKEN or not ADMIN_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": ADMIN_ID, "text": f"🌐 *אתר:* {text}", "parse_mode": "Markdown"})
    except Exception as e:
        print(f"Failed to notify Lina: {e}")

@app.route('/')
def index():
    return "Lina Bot Server is Running!"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    try:
        data = request.json
        user_msg = data.get('message')
        user_id = data.get('user_id', 'guest')

        # אם זו שיחה חדשה
        if user_id not in chat_sessions:
            chat_sessions[user_id] = model.start_chat(history=[])
            notify_lina_telegram(f"🚀 לקוח חדש התחיל שיחה!\nID: {user_id}")

        # שליחת התראה ללינה
        notify_lina_telegram(f"👤 לקוח: {user_msg}")

        # קבלת תשובה מ-Gemini
        chat = chat_sessions[user_id]
        response = chat.send_message(user_msg)
        bot_reply = response.text

        # בדיקה אם הושאר טלפון
        if any(char.isdigit() for char in user_msg) and len(user_msg) > 6:
            notify_lina_telegram(f"🔥 **ליד חם! זוהה טלפון:**\n{user_msg}")

        return jsonify({'reply': bot_reply})

    except Exception as e:
        print(f"Error in web_chat: {e}")
        return jsonify({'reply': "סליחה, יש תקלה רגעית. נסה שוב מאוחר יותר."})

def run_flask():
    """מריץ את השרת בפורט ש-Render דורש"""
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

# === בוט טלגרם (פונקציות) ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("היי! אני הבוט של לינה סוחוביצקי. איך אפשר לעזור?")

async def handle_telegram_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """מטפל בהודעות שנשלחות בטלגרם"""
    user_text = update.message.text
    chat_id = update.effective_chat.id
    
    # שימוש ב-Gemini גם לטלגרם
    try:
        response = model.generate_content(user_text)
        await update.message.reply_text(response.text)
    except:
        await update.message.reply_text("קיבלתי את ההודעה, מעביר ללינה.")

# === הפעלה ראשית ===
if __name__ == "__main__":
    # 1. הפעלת שרת האתר (Flask) ב-Thread נפרד כדי לא לחסום את הטלגרם
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    # 2. הפעלת בוט הטלגרם (Polling)
    if TELEGRAM_TOKEN:
        print("Starting Telegram Bot...")
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_telegram_message))
        
        # הרצה
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    else:
        print("No Telegram Token found. Only Web Server running.")
        # אם אין טוקן, משאירים את הסקריפט חי עבור השרת
        flask_thread.join()
