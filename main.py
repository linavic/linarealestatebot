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
# 🧠 הגדרת המוח של גוגל (הספריה הרשמית והיציבה)
# ==========================================
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    
    # הגדרות בטיחות למניעת חסימות סתמיות
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    # טעינת המודל היציב ביותר (gemini-pro)
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
Context: You might be answering in a public group or private chat.
"""

def ask_google(user_text, history_text):
    """ פונקציה שמשתמשת בספריה הרשמית של גוגל - הכי יציב שיש """
    try:
        # בניית השיחה
        prompt = f"{SYSTEM_PROMPT}\n\nChat History:\n{history_text}\n\nUser: {user_text}\nLina:"
        
        # שליחה
        response = model.generate_content(prompt)
        
        # החזרת טקסט
        return response.text
        
    except Exception as e:
        print(f"💥 Google Error: {e}")
        return "אני בודקת את הפרטים, אחזור אליך מיד."

# ==========================================
# 📩 טיפול בהודעות
# ==========================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    # התעלמות מהודעות מערכת של הערוץ (ID 777000) - זה מה שבד"כ תוקע בוטים בקבוצות דיון
    if update.effective_user.id == 777000: return

    user_text = update.message.text
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type # 'private', 'group', 'supergroup'
    
    print(f"📩 הודעה נכנסה ({chat_type}): {user_text}")

    # חיווי הקלדה - רק בפרטי! (בקבוצות זה יכול לגרום לשגיאות הרשאה)
    if chat_type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    # הרצה ברקע (כדי לא לתקוע את הבוט)
    loop = asyncio.get_running_loop()
    # אנחנו לא שולחים היסטוריה ארוכה כרגע כדי לוודא יציבות מקסימלית
    bot_answer = await loop.run_in_executor(None, ask_google, user_text, "")

    # שליחה לטלגרם - הפרדה בין פרטי לקבוצה
    try:
        if chat_type == 'private':
            # בפרטי: שולחים עם כפתור
            await update.message.reply_text(bot_answer, reply_markup=get_main_keyboard())
        else:
            # בקבוצה: שולחים כ"ציטוט" (Reply) בלי כפתור (כפתורים עושים בעיות בקבוצות לפעמים)
            await update.message.reply_text(bot_answer, quote=True)
            
    except Exception as e:
        print(f"Error sending to Telegram: {e}")
        # ניסיון אחרון לשלוח טקסט נקי
        await update.message.reply_text(bot_answer)

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
        
        print("✅ הבוט רץ! (ספריה רשמית + טיפול בקבוצות)")
        app.run_polling()
