import os
import requests
import logging
import re
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from keep_alive import keep_alive

# ==========================================
# ⚙️ הגדרות
# ==========================================
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_ID = 1687054059

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    print("❌ שגיאה: חסרים מפתחות ב-Secrets!")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

SYSTEM_PROMPT = "את Lina, סוכנת נדל\"ן בנתניה. עני בעברית, קצר ומקצועי."

chats_history = {}

# ==========================================
# 🧠 המקלדת
# ==========================================
def get_main_keyboard():
    button = KeyboardButton("📞 שלח את המספר שלי ללינה", request_contact=True)
    return ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=False)

# ==========================================
# 🧠 חיבור לגוגל ("מפתח מאסטר" - מנסה הכל)
# ==========================================
def send_to_google_direct(history_text, user_text):
    """ מנסה 3 גרסאות שונות של גוגל עד להצלחה """
    
    # רשימת הכתובות האפשריות (מהחדש לישן)
    endpoints = [
        # אופציה 1: המודל הכי חדש (Flash) בגרסת בטא
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
        # אופציה 2: המודל היציב (Pro) בגרסה הרשמית
        f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}",
        # אופציה 3: המודל הישן (1.0 Pro) בגרסת בטא (גיבוי חירום)
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.0-pro:generateContent?key={GEMINI_API_KEY}"
    ]
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nהיסטוריה:\n{history_text}\nלקוח: {user_text}\nאני:"}]
        }]
    }

    last_error = ""

    # לולאה שמנסה את הכתובות אחת אחרי השנייה
    for url in endpoints:
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                # הצלחה! מחזירים את התשובה ויוצאים
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            else:
                last_error = f"Error {response.status_code}: {response.text}"
                print(f"⚠️ ניסיון נכשל בכתובת {url}: {response.status_code}")
                continue # מנסה את הכתובת הבאה
                
        except Exception as e:
            last_error = str(e)
            continue

    # אם כל 3 הכתובות נכשלו
    return f"⚠️ שגיאה סופית בגוגל (כל המודלים נכשלו):\n{last_error}"

# ==========================================
# 📩 הנדלרים
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
    if update.effective_user.id == 777000: return # מונע לופים בערוץ

    user_text = update.message.text
    user_id = update.effective_user.id
    
    # זיהוי טלפון
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    if phone_pattern.search(user_text):
        phone = phone_pattern.search(user_text).group(0)
        await send_lead_alert(context, update.effective_user.first_name, update.effective_user.username, phone, f"טקסט: {user_text}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="רשמתי את המספר, תודה!", reply_markup=get_main_keyboard())

    # היסטוריה
    if user_id not in chats_history: chats_history[user_id] = []
    history = ""
    for msg in chats_history[user_id][-4:]: history += f"{msg['role']}: {msg['text']}\n"

    if update.effective_chat.type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # שליחה לגוגל עם המנגנון החכם
    bot_answer = send_to_google_direct(history, user_text)
    
    chats_history[user_id].append({"role": "user", "text": user_text})
    chats_history[user_id].append({"role": "model", "text": bot_answer})
    
    if update.effective_chat.type == 'private':
        await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer, reply_markup=get_main_keyboard())
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer, reply_to_message_id=update.message.message_id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats_history[update.effective_user.id] = []
    await context.bot.send_message(chat_id=update.effective_chat.id, text="היי! אני לינה נדל\"ן 🏠", reply_markup=get_main_keyboard())

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("✅ הבוט רץ (מצב מפתח מאסטר - מנסה את כל האפשרויות)")
    app.run_polling()
