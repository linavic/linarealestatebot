import os
import logging
import asyncio
import google.generativeai as genai
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters
)
from keep_alive import keep_alive

# ==========================================
# ⚙️ הגדרות
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# לוגים - כדי שנראה מה קורה במסך השחור
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==========================================
# 🧠 הגדרת גוגל (הכי פשוט, הכי יציב)
# ==========================================
if not GEMINI_API_KEY:
    logger.error("❌ חסר מפתח GEMINI_API_KEY!")
else:
    genai.configure(api_key=GEMINI_API_KEY)
    # מודל gemini-pro הוא היחיד שעובד יציב בחינם כרגע
    model = genai.GenerativeModel("gemini-pro")

# ==========================================
# 🧠 הפונקציה שפונה לגוגל
# ==========================================
def ask_gemini(text):
    try:
        # הנחיה לבוט
        prompt = f"את לינה, סוכנת נדלן. עני בעברית בקצרה.\nשאלה: {text}\nתשובה:"
        
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Error from Google: {e}")
        return "יש לי תקלה רגעית, נסה שוב."

# ==========================================
# 📩 טיפול בהודעות
# ==========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    # התעלמות מערוצים (מונע לופים)
    if update.effective_user.id == 777000: return

    text = update.message.text
    chat_type = update.effective_chat.type
    bot_username = context.bot.username

    logger.info(f"📩 הודעה התקבלה ({chat_type}): {text}")

    # --- לוגיקה לקבוצות ---
    # בקבוצה - מגיב רק אם תייגו אותו
    if chat_type in ['group', 'supergroup']:
        if f"@{bot_username}" not in text and not (update.message.reply_to_message and update.message.reply_to_message.from_user.id == context.bot.id):
            return # מתעלם

    # שליחה לגוגל (ברקע)
    loop = asyncio.get_running_loop()
    try:
        response = await loop.run_in_executor(None, ask_gemini, text)
        
        # שליחה חזרה לטלגרם
        if chat_type == 'private':
            await update.message.reply_text(response)
        else:
            await update.message.reply_text(response, quote=True)
            
    except Exception as e:
        logger.error(f"Failed to send message: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("היי, אני לינה! 🏠")

# ==========================================
# 🚀 הרצה
# ==========================================
if __name__ == "__main__":
    keep_alive()

    if not TELEGRAM_BOT_TOKEN:
        print("❌ חסר טוקן של טלגרם!")
    else:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        print("🔄 מנקה חיבורים ישנים...")
        # זה הטריק! מוחק את ה-Webhook התקוע
        # אבל צריך לעשות את זה ידנית ב-Run Polling, אז פשוט נריץ רגיל:
        
        print("✅ הבוט מתחיל לרוץ עכשיו!")
        app.run_polling(drop_pending_updates=True) # מנקה הודעות תקועות
