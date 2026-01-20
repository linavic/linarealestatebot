import os
import logging
import asyncio
import google.generativeai as genai
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from keep_alive import keep_alive

# ==========================================
# ⚙️ הגדרות (Secrets)
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ADMIN_ID = 1687054059

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==========================================
# 🧠 הגדרת המוח של גוגל (הדרך הרשמית)
# ==========================================
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    
    # הגדרות בטיחות (מבטל חסימות מיותרות)
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    # טעינת המודל היציב
    model = genai.GenerativeModel('gemini-pro', safety_settings=safety_settings)
else:
    print("❌ שגיאה: חסר מפתח GEMINI_API_KEY ב-Secrets")

# ==========================================
# 📝 אישיות הבוט
# ==========================================
SYSTEM_PROMPT = """
You are Lina, a real estate agent in Netanya. 
Language: Hebrew.
Traits: Professional, concise, inviting.
Goal: Get the client's phone number or answer property questions.
"""

def ask_google(user_text, history_text):
    """ פונקציה שמשתמשת בספריה הרשמית של גוגל """
    try:
        # בניית השיחה
        prompt = f"{SYSTEM_PROMPT}\n\nChat History:\n{history_text}\n\nUser: {user_text}\nLina:"
        
        # שליחה (הרבה יותר פשוט ויציב)
        response = model.generate_content(prompt)
        
        # החזרת טקסט
        return response.text
        
    except Exception as e:
        # אם יש שגיאה - נראה אותה בלוגים
        print(f"💥 Google Error: {e}")
        return "יש לי תקלה טכנית כרגע, אנא נסה שוב מאוחר יותר."

# ==========================================
# 📩 טיפול בהודעות
# ==========================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    # התעלמות מערוצים
    if update.effective_user.id == 777000: return

    user_text = update.message.text
    user_id = update.effective_user.id
    
    print(f"📩 הודעה נכנסה: {user_text}")

    # חיווי הקלדה
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    # היסטוריה קצרה (לזיכרון)
    # כאן אנחנו לא שומרים הכל כדי לא להכביד, אלא רק את הקונטקסט האחרון
    history = "" 

    # הרצה ברקע (כדי לא לתקוע את הבוט)
    loop = asyncio.get_running_loop()
    bot_answer = await loop.run_in_executor(None, ask_google, user_text, history)

    # שליחה לטלגרם
    try:
        await update.message.reply_text(bot_answer)
    except Exception as e:
        print(f"Error sending to Telegram: {e}")

# ==========================================
# 🎮 פקודות בסיסיות
# ==========================================
def get_main_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("📞 שלח מספר טלפון", request_contact=True)]], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("היי! אני לינה נדל\"ן 🏠", reply_markup=get_main_keyboard())

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.message.contact
    await context.bot.send_message(ADMIN_ID, f"🔔 ליד: {c.phone_number} - {update.effective_user.first_name}")
    await update.message.reply_text("תודה! המספר התקבל.", reply_markup=get_main_keyboard())

# ==========================================
# 🚀 הרצה
# ==========================================
if __name__ == '__main__':
    keep_alive()
    
    if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
        print("❌ חסרים מפתחות ב-Secrets!")
    else:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler('start', start))
        app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        
        print("✅ הבוט רץ! (שיטה רשמית)")
        app.run_polling()
