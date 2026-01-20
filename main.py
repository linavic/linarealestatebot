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
ADMIN_ID = 1687054059  # המזהה שלך לקבלת הלידים

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

SYSTEM_PROMPT = "את Lina, סוכנת נדל\"ן בנתניה. עני בעברית, קצר (עד 2 משפטים) ומקצועי. המטרה: לקבל טלפון."

# ==========================================
# 🧠 המקלדת (הכפתור למטה)
# ==========================================
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📞 שלח מספר טלפון ללינה", request_contact=True)]], 
        resize_keyboard=True
    )

# ==========================================
# 🧠 שליחה לגוגל (V1 יציב)
# ==========================================
def ask_gemini_raw(text):
    # כתובת V1 היציבה
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{"parts": [{"text": f"{SYSTEM_PROMPT}\nUser: {text}"}]}]
    }
    
    try:
        # הגדלתי את ה-Timeout ל-20 שניות כדי למנוע שגיאות 504
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            # גיבוי למקרה של עומס בגוגל
            return "אני בודקת את הפרטים, רגע אחד."
            
    except Exception as e:
        logging.error(f"Connection Error: {e}")
        return "יש לי הפרעה קטנה בקליטה, נסה שוב."

# ==========================================
# 📩 טיפול בהודעות טקסט
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
        answer = await loop.run_in_executor(None, ask_gemini_raw, text)
        
        if chat_type == 'private':
            # בפרטי - שולחים עם הכפתור! (זה מה שהיה חסר)
            await update.message.reply_text(answer, reply_markup=get_main_keyboard())
        else:
            # בקבוצה - רק טקסט
            await update.message.reply_text(answer, quote=True)
            
    except Exception as e:
        logging.error(f"Telegram Error: {e}")

# ==========================================
# 📞 טיפול בשליחת מספר טלפון
# ==========================================
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    user = update.effective_user
    
    # 1. שליחת הליד אליך (למנהל)
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🔔 **ליד חדש!**\n👤 שם: {user.first_name}\n📱 טלפון: `{contact.phone_number}`\n🔗 @{user.username or 'אין'}",
            parse_mode='Markdown'
        )
    except Exception as e:
        logging.error(f"לא הצלחתי לשלוח למנהל: {e}")

    # 2. תודה למשתמש (+ השארת הכפתור למקרה הצורך)
    await update.message.reply_text(
        "תודה! קיבלתי את המספר, לינה תחזור אליך בהקדם. 🏠",
        reply_markup=get_main_keyboard()
    )

# ==========================================
# 🚀 התחלה
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # גם כאן - מוודאים שהכפתור נשלח על ההתחלה
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
        app.add_handler(MessageHandler(filters.CONTACT, handle_contact)) # ✅ הטיפול בכפתור
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        print("✅ הבוט רץ (כולל כפתור אנשי קשר!)")
        app.run_polling()
