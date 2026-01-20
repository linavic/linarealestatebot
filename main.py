import os
import requests
import logging
import re
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from keep_alive import keep_alive

# ==========================================
# ⚙️ הגדרות (מה-Secrets)
# ==========================================
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_ID = 1687054059

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    print("❌ שגיאה: חסרים מפתחות ב-Secrets!")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# הגדרת הפרומפט
SYSTEM_PROMPT = """
You are Lina, a real estate expert in Netanya (Lina Real Estate).
Language: Hebrew.
Tone: Professional, short, and helpful.
Goal: Help clients buy/rent properties or get their phone number.
"""

chats_history = {}

# ==========================================
# 🧠 המקלדת (הכפתור שלא ייעלם)
# ==========================================
def get_main_keyboard():
    button = KeyboardButton("📞 שלח את המספר שלי ללינה", request_contact=True)
    return ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=False)

# ==========================================
# 🧠 חיבור לגוגל (הפונקציה מהקוד שלך - מתוקנת)
# ==========================================
def send_to_google_direct(history_text, user_text):
    """ שולח לגוגל באמצעות requests """
    
    # שינינו ל-v1 ול-gemini-pro כי ה-flash עשה לך שגיאת 404
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nהיסטוריה:\n{history_text}\nלקוח: {user_text}\nאני:"}]
        }]
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            # אם נכשל, נחזיר את השגיאה כדי שתראה
            return f"⚠️ שגיאת גוגל ({response.status_code}):\n{response.text}"
            
    except Exception as e:
        return f"⚠️ תקלה בתקשורת: {str(e)}"

# ==========================================
# 📩 הנדלרים (בדיוק כמו בקוד שלך)
# ==========================================

async def send_lead_alert(context, name, username, phone, source):
    msg = f"🔔 <b>ליד חדש!</b>\n👤 {name}\n📱 {phone}\n📝 {source}"
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode='HTML')
    except: pass

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.message.contact
    await send_lead_alert(context, update.effective_user.first_name, update.effective_user.username, c.phone_number, "כפתור שיתוף")
    await context.bot.send_message(chat_id=update.effective_chat.id, text="תודה! המספר נקלט.", reply_markup=get_main_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    # חובה: הגנה כדי שהבוט לא יענה לעצמו בערוץ (זה מה שגרם ללופים בתמונות שלך)
    if update.effective_user.id == 777000: return

    user_text = update.message.text
    user_id = update.effective_user.id
    
    # זיהוי טלפון בטקסט
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    if phone_pattern.search(user_text):
        phone = phone_pattern.search(user_text).group(0)
        await send_lead_alert(context, update.effective_user.first_name, update.effective_user.username, phone, f"טקסט: {user_text}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="רשמתי את המספר, תודה!", reply_markup=get_main_keyboard())

    # היסטוריה
    if user_id not in chats_history: chats_history[user_id] = []
    history = ""
    for msg in chats_history[user_id][-4:]: history += f"{msg['role']}: {msg['text']}\n"

    # חיווי הקלדה
    if update.effective_chat.type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # שליחה לגוגל
    bot_answer = send_to_google_direct(history, user_text)
    
    chats_history[user_id].append({"role": "user", "text": user_text})
    chats_history[user_id].append({"role": "model", "text": bot_answer})
    
    # תשובה
    if update.effective_chat.type == 'private':
        await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer, reply_markup=get_main_keyboard())
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer, reply_to_message_id=update.message.message_id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats_history[update.effective_user.id] = []
    await context.bot.send_message(chat_id=update.effective_chat.id, text="שלום! אני לינה נדל\"ן 🏠", reply_markup=get_main_keyboard())

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("✅ הבוט רץ (הקוד שלך + תיקון 404)")
    app.run_polling()
