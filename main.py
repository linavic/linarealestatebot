import os
import requests
import logging
import re
import traceback
import time
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from keep_alive import keep_alive

# ==========================================
# 🛑 הגדרות (נא לוודא שהמפתחות מוזנים)
# ==========================================

# נסי להשאיר את זה ככה אם המפתחות בסביבה, או הדביקי בתוך הגרשיים אם צריך
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', "XXX_PASTE_KEY_HERE_XXX")
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', "XXX_PASTE_TOKEN_HERE_XXX")

ADMIN_ID = 1687054059

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# 📝 אישיות הבוט (Lina)
# ==========================================
SYSTEM_PROMPT = """
You are Lina, a real estate expert in Netanya (Lina Real Estate).
Tone: Professional, polite, short, and helpful.
Language: Hebrew (unless spoken to in English/Russian).
Goal: Help clients buy/rent properties in Netanya or get their contact info.

Instructions:
1. If asked about properties, ask for budget and requirements.
2. In group chats, keep answers VERY short (1 sentence).
3. If uncertain, ask to move to WhatsApp or ask for a phone number.
"""

chats_history = {}

# ==========================================
# 🧠 המוח - שליחה לגוגל (עם תיקון השגיאה)
# ==========================================
def send_to_google_direct(history_text, user_text):
    """ מנסה מספר מודלים עד שאחד מצליח """
    
    # רשימת מודלים לניסיון - אם הראשון נכשל (404), הוא יעבור לבא בתור
    models_to_try = [
        "gemini-1.5-flash",       # הכי חדש ומהיר
        "gemini-1.5-flash-001",   # גרסה ספציפית
        "gemini-1.5-pro",         # חזק יותר
        "gemini-pro"              # הישן והכי יציב (פאלבק אחרון)
    ]
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nהיסטוריה:\n{history_text}\nלקוח: {user_text}\nאני:"}]
        }]
    }

    last_error = ""

    for model in models_to_try:
        # שימי לב: שינינו ל-v1beta ולפעמים v1, אבל נשמור על אחידות כרגע
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                # הצלחה!
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                # כישלון במודל הזה, ננסה את הבא
                last_error = f"Error {model}: {response.text[:100]}"
                print(f"⚠️ {model} נכשל ({response.status_code}), מנסה את הבא...")
                continue

        except Exception as e:
            last_error = str(e)
            continue

    # אם יצאנו מהלולאה וכלום לא עבד:
    return f"⚠️ תקלה טכנית: לא ניתן להתחבר למוח כרגע. ({last_error})"

# ==========================================
# 📩 טיפול בהודעות
# ==========================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # סינונים
    if not update.message or not update.message.text: return
    if update.effective_user.id == 777000: return # מתעלם מהודעות אוטומטיות של הערוץ

    user_text = update.message.text
    chat_type = update.effective_chat.type
    
    # 1. זיהוי טלפון (עובד מעולה לפי הצילום מסך שלך!)
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    match = phone_pattern.search(user_text)
    
    if match:
        phone = match.group(0)
        # שליחת ליד למנהל
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID, 
                text=f"🔔 **ליד חדש!**\n📱 `{phone}`\nמקור: {chat_type}\nטקסט: {user_text}",
                parse_mode='Markdown'
            )
        except:
            pass
        
        # תגובה ללקוח
        await update.message.reply_text("תודה! המספר התקבל, לינה תחזור אליך.")
        # ממשיכים ל-AI רק אם יש עוד טקסט, או שאפשר לעצור פה. נמשיך ליתר ביטחון.

    # 2. הכנה ל-AI
    if chat_type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # ניהול היסטוריה
    user_id = update.effective_user.id
    if user_id not in chats_history: chats_history[user_id] = []
    
    history = ""
    for msg in chats_history[user_id][-3:]:
        history += f"{msg['role']}: {msg['text']}\n"

    # 3. שליחה לגוגל (עם הפונקציה החדשה שמחליפה מודלים לבד)
    bot_answer = send_to_google_direct(history, user_text)

    # שמירה בהיסטוריה
    chats_history[user_id].append({"role": "user", "text": user_text})
    chats_history[user_id].append({"role": "model", "text": bot_answer})

    # 4. שליחת התשובה
    try:
        # אם התשובה היא הודעת שגיאה (מתחילה ב-⚠️), נשלח אותה רק למנהל, וללקוח הודעה יפה
        if bot_answer.startswith("⚠️"):
             await context.bot.send_message(chat_id=ADMIN_ID, text=f"🚨 שגיאת מערכת:\n{bot_answer}")
             bot_answer = "אני בודקת את זה רגע, תוכל לכתוב לי בווטסאפ בינתיים?"

        # שליחה ללקוח
        if chat_type == 'private':
             await update.message.reply_text(bot_answer, reply_markup=get_main_keyboard())
        else:
             await update.message.reply_text(bot_answer, quote=True)

    except Exception as e:
        print(f"Error sending to Telegram: {e}")

def get_main_keyboard():
    button = KeyboardButton("📞 שלח את המספר שלי ללינה", request_contact=True)
    return ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=False)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.message.contact
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 **ליד מכפתור!**\n📱 `{c.phone_number}`\nשם: {update.effective_user.first_name}", parse_mode='Markdown')
    await update.message.reply_text("תודה! המספר נשמר.", reply_markup=get_main_keyboard())

# ==========================================
# 🚀 הרצה
# ==========================================
if __name__ == '__main__':
    keep_alive()
    
    if "XXX_" in TELEGRAM_BOT_TOKEN:
        print("❌ נא להגדיר טוקן!")
    else:
        try:
            requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=True")
        except:
            pass

        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler('start', lambda u,c: u.message.reply_text("היי! אני הבוט של לינה.", reply_markup=get_main_keyboard())))
        app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        
        print("✅ הבוט רץ (גרסה מתוקנת עם גיבוי מודלים)")
        app.run_polling()
