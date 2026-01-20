import os
import requests
import logging
import re
import traceback
import asyncio
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from keep_alive import keep_alive

# ==========================================
# ⚙️ הגדרות (מושך מה-Secrets שלך)
# ==========================================
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_ID = 1687054059

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==========================================
# 📝 הגדרות בוט
# ==========================================
SYSTEM_PROMPT = """
You are Lina, a real estate expert in Netanya (Lina Real Estate).
Language: Hebrew.
Tone: Professional, short, and helpful.
Goal: Help clients buy/rent properties or get their phone number.
Important: If the user provides a phone number, thank them and say you will call.
"""
chats_history = {}

# ==========================================
# 🧠 חיבור לגוגל - הגרסה היציבה (v1 + gemini-pro)
# ==========================================
def send_to_google_stable(history_text, user_text):
    """ חיבור למודל היציב ביותר ללא ניסויים """
    
    # שימוש ב-v1 הרגיל ובמודל gemini-pro (הכי אמין שיש)
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nHistory:\n{history_text}\nUser: {user_text}\nAgent:"}]
        }]
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=20)
        
        if response.status_code == 200:
            try:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            except KeyError:
                return "אני בודקת את זה, אשיב לך מיד."
        else:
            # אם יש שגיאה, נחזיר אותה כדי שנדע למה (ולא הודעה גנרית)
            return f"⚠️ שגיאת גוגל ({response.status_code}):\n{response.text[:200]}"

    except Exception as e:
        return f"⚠️ תקלת תקשורת: {str(e)}"

# ==========================================
# 📩 טיפול בהודעות
# ==========================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    # התעלמות מעדכוני מערכת של הערוץ
    if update.effective_user.id == 777000: return

    user_text = update.message.text
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    
    print(f"📩 הודעה: {user_text}")

    # 1. זיהוי מספר טלפון
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    match = phone_pattern.search(user_text)
    if match:
        phone = match.group(0)
        try:
            # שליחת הליד למנהל
            await context.bot.send_message(ADMIN_ID, f"🔔 **ליד חדש!**\n📱 `{phone}`\n💬 {user_text}", parse_mode='Markdown')
        except: pass
        
        await update.message.reply_text("תודה! רשמתי את המספר, לינה תחזור אליך.")
        # ממשיכים ל-AI

    # 2. חיווי הקלדה
    if chat_type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    # 3. היסטוריה
    if user_id not in chats_history: chats_history[user_id] = []
    history = ""
    for msg in chats_history[user_id][-3:]:
        history += f"{msg['role']}: {msg['text']}\n"

    # 4. שליחה לגוגל (ברקע)
    loop = asyncio.get_running_loop()
    bot_answer = await loop.run_in_executor(None, send_to_google_stable, history, user_text)

    # 5. שמירה ושליחה
    chats_history[user_id].append({"role": "user", "text": user_text})
    chats_history[user_id].append({"role": "model", "text": bot_answer})

    try:
        if chat_type == 'private':
            await update.message.reply_text(bot_answer, reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text(bot_answer, quote=True)
    except Exception as e:
        print(f"Error sending msg: {e}")
        # במקרה חירום מנסים לשלוח שוב ללא עיצוב
        await update.message.reply_text(bot_answer)

def get_main_keyboard():
    btn = KeyboardButton("📞 שלח מספר טלפון", request_contact=True)
    return ReplyKeyboardMarkup([[btn]], resize_keyboard=True)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.message.contact
    await context.bot.send_message(ADMIN_ID, f"🔔 ליד מכפתור: {c.phone_number} ({update.effective_user.first_name})")
    await update.message.reply_text("תודה! המספר התקבל.", reply_markup=get_main_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("היי! אני לינה נדל\"ן 🏠\nאיך אפשר לעזור?", reply_markup=get_main_keyboard())

# ==========================================
# 🚀 הרצה
# ==========================================
if __name__ == '__main__':
    keep_alive()
    
    if TELEGRAM_BOT_TOKEN:
        try:
            requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=True")
        except: pass

    if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
         print("❌ שגיאה: מפתחות חסרים!")
    else:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler('start', start))
        app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        
        print("✅ הבוט רץ! (גרסת v1 היציבה)")
        app.run_polling()
