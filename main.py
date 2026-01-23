import os
import logging
import asyncio
import google.generativeai as genai
from telegram import Update
from telegram.constants import ChatAction
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

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    print("❌ שגיאה: חסרים מפתחות ב-Secrets!")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ==========================================
# 🧠 Gemini (הגדרה יציבה ל-Pro)
# ==========================================
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    # שימוש ב-gemini-pro שעובד תמיד
    model = genai.GenerativeModel("gemini-pro")
else:
    model = None

SYSTEM_PROMPT = (
    "את Lina, סוכנת נדל\"ן מקצועית בנתניה. "
    "עני תמיד בעברית. התשובות צריכות להיות מזמינות, מקצועיות וקצרות (עד 3 משפטים)."
    "המטרה שלך היא לעזור ללקוח או לקבל ממנו מספר טלפון."
)

# ==========================================
# 🧠 פונקציית AI
# ==========================================
def ask_gemini(text: str) -> str:
    if not model:
        return "שגיאת הגדרות במערכת."
        
    try:
        # ב-gemini-pro ישנים, עדיף לשלוח את ההנחיה בתוך הטקסט
        full_prompt = f"{SYSTEM_PROMPT}\n\nUser Question: {text}\nLina Answer:"
        
        response = model.generate_content(full_prompt)

        if not response or not response.text:
            return "אני בודקת את זה רגע..."

        return response.text.strip()

    except Exception as e:
        logging.error(f"Gemini Error: {e}")
        return "יש לי תקלה טכנית רגעית, נסה שוב עוד דקה."

# ==========================================
# 📩 הודעות
# ==========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # סינונים בסיסיים
    if not update.message or not update.message.text: return
    if update.effective_user.id == 777000: return # התעלמות מערוצים

    user_text = update.message.text
    chat_type = update.effective_chat.type
    bot_username = context.bot.username

    # --- לוגיקה לקבוצות ---
    # אם אנחנו בקבוצה, נענה רק אם תייגו אותנו או הגיבו לנו
    if chat_type in ['group', 'supergroup']:
        is_reply = (update.message.reply_to_message and 
                    update.message.reply_to_message.from_user.id == context.bot.id)
        is_mention = f"@{bot_username}" in user_text
        
        if not (is_reply or is_mention):
            return # שתיקה (לא עונים להודעות כלליות בקבוצה)

    # חיווי הקלדה (רק בפרטי)
    if chat_type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # הרצה ברקע כדי לא לתקוע את הבוט
    loop = asyncio.get_running_loop()
    answer = await loop.run_in_executor(None, ask_gemini, user_text)
    
    # שליחה
    if chat_type == 'private':
        await update.message.reply_text(answer)
    else:
        # בקבוצה תמיד עם ציטוט
        await update.message.reply_text(answer, quote=True)

# ==========================================
# 🚀 פקודת start
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 שלום! אני Lina, סוכנת נדל\"ן בנתניה.\n"
        "איך אפשר לעזור לך היום?"
    )

# ==========================================
# ▶️ הרצה
# ==========================================
if __name__ == "__main__":
    keep_alive()

    if not TELEGRAM_BOT_TOKEN:
        print("❌ הבוט לא יכול לרוץ בלי טוקן")
    else:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        print("🤖 Bot is running (Lina - Stable Version)...")
        app.run_polling()
