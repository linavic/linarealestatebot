import os
import requests
import logging
import re
import traceback
import asyncio
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from keep_alive import keep_alive

# ==========================================
# ⚙️ הגדרות
# ==========================================
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_ID = 1687054059

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==========================================
# 🧠 חיבור לגוגל - מצב "חשיפת שגיאות"
# ==========================================
def send_to_google_diagnostic(history_text, user_text):
    """ הפונקציה הזו לא מסתירה שגיאות, אלא שולחת אותן ישירות למשתמש """
    
    # בדיקה שהמפתח קיים
    if not GEMINI_API_KEY:
        return "⚠️ שגיאה: המפתח GEMINI_API_KEY חסר בהגדרות השרת (Environment Variables)."

    # אנחנו ננסה רק מודל אחד כדי לקבל את השגיאה המדויקת עליו
    model = "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"You are a real estate agent.\nUser says: {user_text}\nAnswer:"}]
        }]
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        # אם הכל תקין - מחזירים תשובה
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        
        # === כאן השינוי: אם יש שגיאה, מחזירים אותה למשתמש ===
        else:
            return f"⚠️ **Google Raw Error ({response.status_code}):**\n\n`{response.text}`"

    except Exception as e:
        return f"⚠️ **Connection Error:**\n`{str(e)}`"

# ==========================================
# 📩 הנדלרים
# ==========================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    # חיווי הקלדה
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    user_text = update.message.text
    
    # הרצה ברקע
    loop = asyncio.get_running_loop()
    bot_answer = await loop.run_in_executor(None, send_to_google_diagnostic, "", user_text)

    # שליחת התשובה (או השגיאה)
    try:
        await update.message.reply_text(bot_answer, parse_mode='Markdown')
    except:
        # אם יש בעיה בעיצוב, שולחים כטקסט פשוט
        await update.message.reply_text(bot_answer)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("מצב דיאגנוסטיקה מופעל. שלח הודעה כדי לבדוק את החיבור לגוגל.")

# ==========================================
# 🚀 הרצה
# ==========================================
if __name__ == '__main__':
    keep_alive()
    
    if not TELEGRAM_BOT_TOKEN:
        print("Error: No Telegram Token")
    else:
        # ניקוי
        try:
            requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=True")
        except: pass

        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler('start', start))
        app.add_handler(MessageHandler(filters.TEXT, handle_message))
        
        print("✅ הבוט במצב דיאגנוסטיקה. נא לשלוח הודעה.")
        app.run_polling()
