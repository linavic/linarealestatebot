import os
import logging
import asyncio
import google.generativeai as genai
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
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
ADMIN_ID = 1687054059

# לוגים - כדי לראות במסך השחור אם יש שגיאה
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==========================================
# 🧠 הגדרת גוגל (מודל Flash המהיר)
# ==========================================
if not GEMINI_API_KEY:
    print("❌ שגיאה: חסר מפתח גוגל")
else:
    genai.configure(api_key=GEMINI_API_KEY)
    # משתמשים ב-Flash שהוא המהיר והיציב ביותר כרגע
    model = genai.GenerativeModel("gemini-1.5-flash")

SYSTEM_PROMPT = "את Lina, סוכנת נדל\"ן בנתניה. עני בעברית, קצר (עד 2 משפטים) ומקצועי. המטרה: לקבל טלפון."

# ==========================================
# 🎮 כפתור שליחת טלפון
# ==========================================
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📞 שלח טלפון ללינה (לחץ כאן)", request_contact=True)]], 
        resize_keyboard=True
    )

# ==========================================
# 🧠 שליחה לגוגל
# ==========================================
def ask_gemini(text):
    try:
        # פניה דרך הספריה הרשמית
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
    
    # התעלמות מערוצים
    if update.effective_user.id == 777000: return 

    text = update.message.text
    chat_type = update.effective_chat.type
    bot_username = context.bot.username

    # --- סינון קבוצות ---
    if chat_type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        is_mentioned = f"@{bot_username}" in text
        is_reply = (update.message.reply_to_message and 
                    update.message.reply_to_message.from_user.id == context.bot.id)
        
        if not (is_mentioned or is_reply):
            return 

        text = text.replace(f"@{bot_username}", "").strip()

    # חיווי הקלדה
    if chat_type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # שליחה לגוגל ברקע
    loop = asyncio.get_running_loop()
    try:
        answer = await loop.run_in_executor(None, ask_gemini, text)
        
        if chat_type == 'private':
            await update.message.reply_text(answer, reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text(answer, quote=True)
            
    except Exception as e:
        logging.error(f"Error: {e}")

# ==========================================
# 📞 טיפול בליד (טלפון)
# ==========================================
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    user = update.effective_user
    
    # שליחה למנהל
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔔 **ליד חדש!**\n👤 {user.first_name}\n📱 `{contact.phone_number}`",
            parse_mode='Markdown'
        )
    except: pass

    await update.message.reply_text(
        "תודה! קיבלתי את המספר, אחזור אליך בהקדם. 🏠",
        reply_markup=get_main_keyboard()
    )

# ==========================================
# 🚀 התחלה
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "היי! אני לינה 🏠\nבמה אפשר לעזור?",
        reply_markup=get_main_keyboard()
    )

if __name__ == "__main__":
    keep_alive()

    if not TELEGRAM_BOT_TOKEN:
        print("❌ חסר טוקן")
    else:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        print("🧹 מנקה הודעות ישנות...")
        # הפקודה הזו מנקה את כל התקיעות!
        app.run_polling(drop_pending_updates=True)
        print("✅ הבוט אופס ומוכן לעבודה!")

