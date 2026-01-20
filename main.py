import os
import requests
import logging
import re
import asyncio
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from keep_alive import keep_alive

# ==========================================
# ⚙️ הגדרות (מושך מה-Secrets)
# ==========================================
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_ID = 1687054059

# הגדרת לוגים בסיסית
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==========================================
# 📝 הגדרות בוט
# ==========================================
SYSTEM_PROMPT = "You are Lina, a real estate agent in Netanya. Be helpful, professional and concise. Speak Hebrew."
chats_history = {}

# ==========================================
# 🧠 חיבור לגוגל - הגרסה הישנה והבטוחה (v1)
# ==========================================
def send_to_google_classic(history_text, user_text):
    """ חיבור למודל gemini-pro בגרסת v1 (הכי יציבה) """
    
    # זו הכתובת שעבדה בעבר בוודאות
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nHistory:\n{history_text}\nUser: {user_text}\nAgent:"}]
        }],
        # מבטל חסימות בטיחות שגורמות לשגיאות סתם
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }

    try:
        # Timeout ארוך יותר (30 שניות) למקרה שגוגל איטי
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"⚠️ שגיאת גוגל: {response.status_code} - {response.text}")
            return "יש לי תקלה טכנית כרגע. אנא נסה שוב מאוחר יותר."

    except Exception as e:
        print(f"💥 שגיאת חיבור: {e}")
        return "שגיאת תקשורת. נא לנסות שוב."

# ==========================================
# 📩 טיפול בהודעות
# ==========================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # סינונים
    if not update.message or not update.message.text: return
    if update.effective_user.id == 777000: return

    user_text = update.message.text
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    
    # 1. זיהוי טלפון
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    match = phone_pattern.search(user_text)
    if match:
        phone = match.group(0)
        try:
            await context.bot.send_message(ADMIN_ID, f"🔔 ליד חדש: {phone}\n{user_text}")
        except: pass
        await update.message.reply_text("תודה! רשמתי את המספר.")

    # 2. חיווי הקלדה (רק בפרטי)
    if chat_type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    # 3. ניהול היסטוריה
    if user_id not in chats_history: chats_history[user_id] = []
    history = ""
    for msg in chats_history[user_id][-3:]:
        history += f"{msg['role']}: {msg['text']}\n"

    # 4. שליחה לגוגל (ברקע - קריטי!)
    loop = asyncio.get_running_loop()
    bot_answer = await loop.run_in_executor(None, send_to_google_classic, history, user_text)

    # 5. שמירה ושליחה
    chats_history[user_id].append({"role": "user", "text": user_text})
    chats_history[user_id].append({"role": "model", "text": bot_answer})

    try:
        if chat_type == 'private':
            await update.message.reply_text(bot_answer, reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text(bot_answer, quote=True)
    except Exception as e:
        print(f"Error sending to Telegram: {e}")
        await update.message.reply_text(bot_answer)

def get_main_keyboard():
    btn = KeyboardButton("📞 שלח מספר טלפון", request_contact=True)
    return ReplyKeyboardMarkup([[btn]], resize_keyboard=True)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.message.contact
    await context.bot.send_message(ADMIN_ID, f"🔔 ליד מכפתור: {c.phone_number}")
    await update.message.reply_text("תודה! המספר התקבל.", reply_markup=get_main_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("היי! אני לינה.", reply_markup=get_main_keyboard())

# ==========================================
# 🚀 הרצה
# ==========================================
if __name__ == '__main__':
    keep_alive()
    
    # מנקה וובהוקים ישנים
    if TELEGRAM_BOT_TOKEN:
        try:
            requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=True")
        except: pass

    if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
         print("❌ שגיאה: מפתחות חסרים ב-Secrets!")
    else:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler('start', start))
        app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        
        print("✅ הבוט רץ! (מודל קלאסי v1)")
        app.run_polling()
