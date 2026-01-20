import os
import logging
import asyncio
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

# לוגים בסיסיים
logging.basicConfig(level=logging.INFO)

# ==========================================
# 🧠 הגדרת המוח של גוגל (הספריה הרשמית)
# ==========================================
if not GEMINI_API_KEY:
    print("❌ שגיאה: חסר מפתח GEMINI_API_KEY")
else:
    genai.configure(api_key=GEMINI_API_KEY)
    
    # משתמשים במודל המהיר והעדכני ביותר
    # אם זה עדיין עושה 404, סימן שהמפתח שלך לא תומך בו, ונחליף ל-gemini-pro
    model = genai.GenerativeModel("gemini-1.5-flash")

SYSTEM_PROMPT = (
    "את Lina, סוכנת נדל\"ן מקצועית בנתניה. "
    "עני בעברית, בצורה קצרה (עד 2 משפטים) ומזמינה. "
    "המטרה: לעזור ללקוח או לקבל טלפון."
)

# ==========================================
# 🧠 פונקציה לשליחה לגוגל
# ==========================================
def ask_gemini(text: str) -> str:
    try:
        # שליחה פשוטה ונקייה דרך הספריה הרשמית
        prompt = f"{SYSTEM_PROMPT}\nUser: {text}\nLina:"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        # במקרה של שגיאה, מדפיסים ללוג ומחזירים הודעה נעימה
        logging.error(f"Gemini Error: {e}")
        return "אני בודקת את הפרטים, אחזור אליך מיד."

# ==========================================
# 📩 טיפול בהודעות
# ==========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    # מניעת לופים מערוצים
    if update.effective_user.id == 777000: return

    text = update.message.text
    chat_type = update.effective_chat.type
    bot_username = context.bot.username

    # --- סינון קבוצות (החלק החשוב!) ---
    if chat_type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        # בודק אם תייגו את הבוט או הגיבו לו
        is_mentioned = f"@{bot_username}" in text
        is_reply = (update.message.reply_to_message and 
                    update.message.reply_to_message.from_user.id == context.bot.id)
        
        if not (is_mentioned or is_reply):
            return # אם לא פנו אלינו, אנחנו שותקים בקבוצה!

        # ניקוי השם של הבוט מההודעה כדי לא לבלבל את גוגל
        text = text.replace(f"@{bot_username}", "").strip()

    # חיווי הקלדה (רק בפרטי)
    if chat_type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # שליחה לגוגל ברקע
    loop = asyncio.get_running_loop()
    try:
        answer = await loop.run_in_executor(None, ask_gemini, text)
        
        if chat_type == 'private':
            await update.message.reply_text(answer)
        else:
            await update.message.reply_text(answer, quote=True)
            
    except Exception as e:
        print(f"Error: {e}")

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

        print("✅ הבוט רץ! (גרסה רשמית)")
        app.run_polling()
