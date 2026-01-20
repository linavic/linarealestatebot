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

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==========================================
# 🧠 הגדרת גוגל (מנגנון מודל כפול)
# ==========================================
if not GEMINI_API_KEY:
    print("❌ שגיאה: חסר מפתח GEMINI_API_KEY")
else:
    genai.configure(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = "את Lina, סוכנת נדל\"ן בנתניה. עני בעברית, קצר (עד 2 משפטים) ומקצועי. המטרה: לקבל טלפון."

def ask_gemini_stable(text):
    """ מנסה את המודל החדש, ואם נכשל - עובר לישן """
    try:
        # ניסיון ראשון: המודל המהיר (Flash)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(f"{SYSTEM_PROMPT}\nUser: {text}")
        return response.text.strip()
    except Exception as e:
        logging.warning(f"Flash failed ({e}), trying Pro...")
        try:
            # ניסיון שני: המודל הישן והיציב (1.0 Pro)
            model_backup = genai.GenerativeModel("gemini-1.0-pro")
            response = model_backup.generate_content(f"{SYSTEM_PROMPT}\nUser: {text}")
            return response.text.strip()
        except Exception as e2:
            logging.error(f"Both models failed: {e2}")
            return "אני בודקת את הפרטים, רגע אחד."

# ==========================================
# 🎮 המקלדת (הכפתור למטה)
# ==========================================
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📞 שלח טלפון ללינה (לחץ כאן)", request_contact=True)]], 
        resize_keyboard=True
    )

# ==========================================
# 📩 טיפול בהודעות
# ==========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
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

    # חיווי הקלדה (רק בפרטי)
    if chat_type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # שליחה לגוגל
    loop = asyncio.get_running_loop()
    try:
        answer = await loop.run_in_executor(None, ask_gemini_stable, text)
        
        if chat_type == 'private':
            # בפרטי - תמיד עם הכפתור!
            await update.message.reply_text(answer, reply_markup=get_main_keyboard())
        else:
            # בקבוצה - ציטוט
            await update.message.reply_text(answer, quote=True)
            
    except Exception as e:
        logging.error(f"Telegram Error: {e}")

# ==========================================
# 📞 טיפול בליד (טלפון)
# ==========================================
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    user = update.effective_user
    
    # 1. שליחת התראה למנהל
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔔 **ליד חדש!**\n👤 {user.first_name}\n📱 `{contact.phone_number}`",
            parse_mode='Markdown'
        )
    except: pass

    # 2. תודה למשתמש
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

        print("✅ הבוט רץ (גרסה יציבה עם גיבוי אוטומטי)")
        app.run_polling()
