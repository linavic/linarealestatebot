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
# 🧠 הגדרת המוח של גוגל (הספריה הרשמית)
# ==========================================
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    
    # שימוש במודל gemini-pro היציב
    model = genai.GenerativeModel(
        'gemini-pro', 
        safety_settings=safety_settings,
        generation_config={"temperature": 0.7, "max_output_tokens": 400}
    )
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
Keep responses SHORT (max 2-3 sentences).
"""

def ask_google(user_text, history_text):
    """ פונקציה לשליחה לגוגל עם הגנת Timeout """
    try:
        prompt = f"{SYSTEM_PROMPT}\n\nChat History:\n{history_text}\n\nUser: {user_text}\nLina:"
        
        # הגבלה של 10 שניות כדי שהבוט לא יתקע
        response = model.generate_content(prompt, request_options={'timeout': 10})
        return response.text
        
    except Exception as e:
        logging.error(f"💥 Google Error: {e}")
        return "אני בודקת את הפרטים, אחזור אליך מיד 🏠"

# ==========================================
# 📩 טיפול בהודעות
# ==========================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # סינונים בסיסיים
    if not update.message or not update.message.text: return
    
    # --- סינון קריטי לערוצים ---
    # מונע מהבוט לענות לפוסטים של הערוץ עצמו (מונע לופים)
    if update.effective_user.id == 777000: 
        return

    user_text = update.message.text
    chat_type = update.effective_chat.type
    
    logging.info(f"📩 הודעה ({chat_type}): {user_text}")

    # חיווי הקלדה (רק בפרטי, כדי לא לשגע את הקבוצה)
    if chat_type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    # קבלת תשובה מגוגל (ברקע)
    loop = asyncio.get_running_loop()
    
    # ניהול זיכרון חכם (שימוש ב-chat_data)
    if 'chat_history' not in context.chat_data:
        context.chat_data['chat_history'] = []
    
    # לוקחים רק את 3 ההודעות האחרונות להיסטוריה
    recent_history = "\n".join(context.chat_data['chat_history'][-3:])
    
    try:
        bot_answer = await loop.run_in_executor(None, ask_google, user_text, recent_history)
    except Exception as e:
        logging.error(f"שגיאה כללית: {e}")
        bot_answer = "סליחה, יש לי תקלה רגעית."

    # עדכון ההיסטוריה
    context.chat_data['chat_history'].append(f"User: {user_text}")
    context.chat_data['chat_history'].append(f"Lina: {bot_answer}")
    
    # שמירה על זיכרון קצר (עד 10 שורות)
    if len(context.chat_data['chat_history']) > 10:
        context.chat_data['chat_history'] = context.chat_data['chat_history'][-10:]

    # שליחה לטלגרם
    try:
        if chat_type == 'private':
            await update.message.reply_text(bot_answer, reply_markup=get_main_keyboard())
        else:
            # בקבוצה - תמיד עם "Reply" (ציטוט)
            await update.message.reply_text(bot_answer, quote=True)
            
    except Exception as e:
        logging.error(f"שגיאה בשליחה: {e}")

# ==========================================
# 🎮 פקודות ותפריטים
# ==========================================
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📞 שלח מספר טלפון", request_contact=True)]], 
        resize_keyboard=True
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = "היי! 👋 אני לינה, סוכנת נדל\"ן בנתניה 🏠\n\nאשמח לעזור לך למצוא את הנכס המושלם!"
    await update.message.reply_text(welcome_msg, reply_markup=get_main_keyboard())

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.message.contact
    user_name = update.effective_user.first_name or "לקוח"
    
    # שליחה לאדמין
    try:
        await context.bot.send_message(
            ADMIN_ID, 
            f"🔔 ליד חדש!\n👤 {user_name}\n📞 {c.phone_number}"
        )
    except: pass
    
    await update.message.reply_text(
        "תודה רבה! 🙏\nקיבלתי את הפרטים ואחזור אליך בהקדם.",
        reply_markup=get_main_keyboard()
    )

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
        
        print("✅ הבוט רץ! (גרסה סופית ויציבה)")
        app.run_polling()
