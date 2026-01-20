import os
import requests
import logging
import re
import traceback
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from keep_alive import keep_alive

# ==========================================
# 🛑 הגדרות חובה (נא למלא כאן אם זה לא עובד דרך הסביבה)
# ==========================================

# הכניסי את המפתחות שלך בתוך הגרשיים במקום ה-XXX
# (אם את בטוחה שהם מוגדרים בשרת, תשאירי את os.environ)
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', "XXX_PASTE_GOOGLE_KEY_HERE_XXX")
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', "XXX_PASTE_BOT_TOKEN_HERE_XXX")

ADMIN_ID = 1687054059  # המספר שלך לקבלת דיווח על שגיאות

# הגדרת לוגים מפורטים
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# 📝 הגדרת הבוט (Lina Persona)
# ==========================================
SYSTEM_PROMPT = """
You are Lina, a real estate expert in Netanya (Lina Real Estate).
Details:
- Name: Lina Sukhovitsky
- Phone: 054-4326270
- Email: office@linarealestate.net
- Website: linarealestate.net
- Focus: Luxury apartments, sales, rentals, investments in Netanya.
- Tone: Professional, polite, helpful, short and concise.

Important Instructions:
1. If the user asks for a property, ask for their budget and preferences.
2. If in a group chat, keep answers very short (1-2 sentences).
3. Always offer to move to WhatsApp for urgent matters.
"""

chats_history = {}

# ==========================================
# 🧠 המוח - שליחה לגוגל (עם דיווח שגיאות)
# ==========================================
def send_to_google_direct(history_text, user_text):
    """ שולח לגוגל ומחזיר תשובה. אם נכשל - מחזיר את השגיאה """
    
    # בדיקה שהמפתח תקין
    if "XXX_" in GEMINI_API_KEY:
        return "⚠️ שגיאה קריטית: לא הגדרת את המפתח של גוגל (GEMINI_API_KEY) בקוד."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nהיסטוריה:\n{history_text}\nלקוח: {user_text}\nאני:"}]
        }]
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            error_msg = f"⚠️ שגיאה מגוגל ({response.status_code}): {response.text[:200]}"
            logger.error(error_msg)
            return error_msg

    except Exception as e:
        return f"⚠️ שגיאת חיבור לאינטרנט: {str(e)}"

# ==========================================
# 📩 טיפול בהודעות (מנגנון ראשי)
# ==========================================

async def send_admin_error(context, error_text):
    """ שולח הודעה ללינה שיש תקלה בבוט """
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 **תקלה בבוט:**\n{error_text}", parse_mode='Markdown')
    except:
        logger.error("לא הצלחתי לשלוח הודעת שגיאה למנהל")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # 1. סינונים
        if not update.message or not update.message.text: return
        # התעלמות מפוסטים אוטומטיים של הערוץ (משתמש 777000)
        if update.effective_user.id == 777000: return

        user_text = update.message.text
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type
        
        logger.info(f"הודעה התקבלה מ-{user_id} ({chat_type}): {user_text}")

        # 2. זיהוי טלפון
        phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
        match = phone_pattern.search(user_text)
        if match:
            phone = match.group(0)
            alert_msg = f"🔔 **ליד חדש!**\n📱 טלפון: `{phone}`\n💬 טקסט: {user_text}\n📍 מקור: {chat_type}"
            await context.bot.send_message(chat_id=ADMIN_ID, text=alert_msg, parse_mode='Markdown')
            
            # תגובה קצרה ללקוח
            await update.message.reply_text("תודה! רשמתי את המספר, לינה תחזור אליך.")
            # ממשיכים ל-AI למקרה שיש שאלה

        # 3. הכנה ל-AI
        if chat_type == 'private':
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
        
        # ניהול היסטוריה
        if user_id not in chats_history: chats_history[user_id] = []
        history = ""
        for msg in chats_history[user_id][-3:]:
            history += f"{msg['role']}: {msg['text']}\n"

        # 4. שליחה לגוגל
        bot_answer = send_to_google_direct(history, user_text)

        # 5. בדיקה אם חזרה שגיאה
        if bot_answer.startswith("⚠️"):
            # שולח את השגיאה למנהל בלבד
            await send_admin_error(context, bot_answer)
            # ללקוח עונים בנימוס
            bot_answer = "סליחה, יש לי תקלה רגעית בתקשורת. אנא נסה שוב או שלח הודעה לווטסאפ."

        # שמירה בהיסטוריה
        chats_history[user_id].append({"role": "user", "text": user_text})
        chats_history[user_id].append({"role": "model", "text": bot_answer})

        # 6. שליחה חזרה לטלגרם
        # חשוב: בקבוצות עונים עם quote=True כדי שהמשתמש יבין למי ענינו
        await update.message.reply_text(bot_answer, quote=True)

    except Exception as e:
        # תופס כל קריסה אפשרית ושולח לך דיווח
        error_trace = traceback.format_exc()
        logger.error(f"CRITICAL ERROR: {error_trace}")
        await send_admin_error(context, f"קריסה כללית בקוד:\n`{str(e)}`")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("היי! אני לינה נדל\"ן. איך אפשר לעזור?")

# ==========================================
# 🚀 הרצה
# ==========================================
if __name__ == '__main__':
    keep_alive()
    
    if "XXX_" in TELEGRAM_BOT_TOKEN:
        print("❌ שגיאה: לא הגדרת את הטוקן של הבוט בשורה 15!")
    else:
        try:
            # מנקה וובהוקים ישנים
            requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=True")
        except:
            pass

        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler('start', start))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        
        print("✅ הבוט רץ! נסי לשלוח הודעה.")
        app.run_polling()
