import os
import logging
import google.generativeai as genai
from telegram import Update
from telegram.constants import ChatAction, ChatType
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

# לוגים נקיים
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==========================================
# 🧠 הגדרת גוגל (הגרסה היציבה שעבדה)
# ==========================================
if not GEMINI_API_KEY:
    print("❌ שגיאה: חסר מפתח גוגל")
else:
    genai.configure(api_key=GEMINI_API_KEY)
    
    # חזרה למודל gemini-pro (היציב ביותר, בלי שגיאות 404)
    model = genai.GenerativeModel("gemini-pro")

SYSTEM_PROMPT = "את לינה, סוכנת נדל\"ן בנתניה. עני בעברית, קצר ולעניין."

# ==========================================
# 🧠 פונקציה לשליחה לגוגל
# ==========================================
def ask_gemini(text):
    try:
        # שליחה ישירה ופשוטה
        response = model.generate_content(f"{SYSTEM_PROMPT}\nUser: {text}")
        return response.text.strip()
    except Exception as e:
        logging.error(f"Gemini Error: {e}")
        return "אני בודקת את הפרטים, רגע אחד."

# ==========================================
# 📩 טיפול בהודעות
# ==========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    if update.effective_user.id == 777000: return # הגנה מערוצים

    text = update.message.text
    chat_type = update.effective_chat.type
    bot_username = context.bot.username

    # --- הלוגיקה שעבדה בקבוצות ---
    # אם אנחנו בקבוצה - נתעלם אלא אם כן פנו אלינו ישירות
    if chat_type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        is_mentioned = f"@{bot_username}" in text
        is_reply = (update.message.reply_to_message and 
                    update.message.reply_to_message.from_user.id == context.bot.id)
        
        if not (is_mentioned or is_reply):
            return 

        # מנקה את שם הבוט מההודעה
        text = text.replace(f"@{bot_username}", "").strip()

    # חיווי הקלדה (רק בפרטי)
    if chat_type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # תשובה
    try:
        response = ask_gemini(text)
        
        if chat_type == 'private':
            await update.message.reply_text(response)
        else:
            await update.message.reply_text(response, quote=True)
            
    except Exception as e:
        print(f"Error: {e}")

# ==========================================
# 🚀 התחלה
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("היי, אני לינה. איך אפשר לעזור?")

if __name__ == "__main__":
    keep_alive()

    if not TELEGRAM_BOT_TOKEN:
        print("❌ חסר טוקן")
    else:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        print("✅ הבוט רץ (הגרסה היציבה שביקשת)")
        app.run_polling()
