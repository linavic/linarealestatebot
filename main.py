import os
import logging
import requests
import asyncio
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

# לוגים
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

SYSTEM_PROMPT = "את Lina, סוכנת נדל\"ן בנתניה. עני בעברית, קצר ומקצועי."

# ==========================================
# 🧠 פונקציה לשליחה לגוגל (השיטה הישנה והטובה)
# ==========================================
def ask_gemini_raw(text):
    # כתובת V1 היציבה - עוקפת את כל הבעיות של הספריה
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": f"{SYSTEM_PROMPT}\nUser: {text}"}]}]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            # אם gemini-pro נכשל, ננסה את 1.5-flash כגיבוי באותה שיטה
            logging.error(f"Gemini Pro failed ({response.status_code}), trying Flash...")
            url_flash = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
            response = requests.post(url_flash, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            
            return "אני בודקת את זה, רגע אחד."
            
    except Exception as e:
        logging.error(f"Connection Error: {e}")
        return "תקלה בתקשורת, נסה שוב."

# ==========================================
# 📩 טיפול בהודעות
# ==========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    if update.effective_user.id == 777000: return 

    text = update.message.text
    chat_type = update.effective_chat.type
    bot_username = context.bot.username

    # --- סינון קבוצות (החלק החכם) ---
    if chat_type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        is_mentioned = f"@{bot_username}" in text
        is_reply = (update.message.reply_to_message and 
                    update.message.reply_to_message.from_user.id == context.bot.id)
        
        if not (is_mentioned or is_reply):
            return # שתיקה בקבוצה אם לא פנו אלינו

        text = text.replace(f"@{bot_username}", "").strip()

    # חיווי הקלדה (רק בפרטי)
    if chat_type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # שליחה
    loop = asyncio.get_running_loop()
    try:
        answer = await loop.run_in_executor(None, ask_gemini_raw, text)
        
        if chat_type == 'private':
            await update.message.reply_text(answer)
        else:
            await update.message.reply_text(answer, quote=True)
            
    except Exception as e:
        logging.error(f"Telegram Error: {e}")

# ==========================================
# 🚀 התחלה
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("היי! אני לינה 🏠")

if __name__ == "__main__":
    keep_alive()

    if not TELEGRAM_BOT_TOKEN:
        print("❌ חסר טוקן")
    else:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        print("✅ הבוט רץ (החיבור הישן + תיקון קבוצות)")
        app.run_polling()
