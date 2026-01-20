import os
import logging
import requests
import asyncio
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

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

SYSTEM_PROMPT = "את Lina, סוכנת נדל\"ן בנתניה. עני בעברית, קצר ומקצועי. המטרה: לקבל טלפון."

# ==========================================
# 🎮 כפתור (קבוע!)
# ==========================================
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📞 שלח מספר טלפון ללינה", request_contact=True)]], 
        resize_keyboard=True
    )

# ==========================================
# 🧠 חיבור לגוגל (השיטה הידנית והבטוחה)
# ==========================================
def ask_gemini_final(text):
    # 1. ניסיון ראשון: הכתובת הישנה והיציבה (V1 gemini-pro)
    # זו הכתובת שעבדה לך בהתחלה!
    url_v1 = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    
    # 2. ניסיון שני: המודל החדש (Flash) במידה והראשון נכשל
    url_flash = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": f"{SYSTEM_PROMPT}\nUser: {text}"}]}]
    }
    
    try:
        # מנסים את ה-V1 הישן והטוב
        # timeout של 30 שניות כדי למנוע את שגיאת ה-504 שראית
        response = requests.post(url_v1, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            logging.warning(f"V1 Pro failed ({response.status_code}), trying Flash...")
            # אם נכשל (404/500) - מנסים את הפלאש
            response = requests.post(url_flash, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            
            # אם שניהם נכשלו - מחזירים את השגיאה האמיתית כדי שתדעי (במקום "בודקת פרטים")
            return f"⚠️ שגיאה כפולה בגוגל. קוד: {response.status_code}"

    except Exception as e:
        return f"⚠️ שגיאת חיבור: {str(e)}"

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

    # חיווי הקלדה
    if chat_type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # שליחה לגוגל
    loop = asyncio.get_running_loop()
    try:
        answer = await loop.run_in_executor(None, ask_gemini_final, text)
        
        if chat_type == 'private':
            # בפרטי: שולחים תשובה + מוודאים שהכפתור שם
            await update.message.reply_text(answer, reply_markup=get_main_keyboard())
        else:
            # בקבוצה: רק ציטוט
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
        "תודה! קיבלתי את המספר.",
        reply_markup=get_main_keyboard()
    )

# ==========================================
# 🚀 התחלה
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "היי! אני לינה 🏠",
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

        print("✅ הבוט רץ (הגרסה הישנה והיציבה!)")
        app.run_polling(drop_pending_updates=True)
