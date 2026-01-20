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
# ⚙️ הגדרות (נלקח אוטומטית מה-Secrets)
# ==========================================

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_ID = 1687054059

# בדיקה שהמפתחות קיימים (מונע קריסה שקטה)
if not GEMINI_API_KEY or not TELEGRAM_BOT_TOKEN:
    print("❌ שגיאה קריטית: המפתחות לא נמצאו ב-Secrets/Environment Variables!")
    # לא עוצרים את הקוד כדי שתראי את השגיאה, אבל הבוט לא יעבוד בלי זה

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

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
# 🧠 חיבור לגוגל (רץ ברקע)
# ==========================================
def send_to_google_blocking(history_text, user_text):
    """ הפונקציה הזו רצה ברקע כדי לא לתקוע את הבוט """
    
    # רשימת מודלים לגיבוי
    models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-1.0-pro"]
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nHistory:\n{history_text}\nUser: {user_text}\nAgent:"}]
        }]
    }

    last_error = ""

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        try:
            # timeout=10 מונע מהבוט לחכות לנצח
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 200:
                try:
                    return response.json()['candidates'][0]['content']['parts'][0]['text']
                except KeyError:
                    continue 
            else:
                print(f"⚠️ מודל {model} נכשל, עובר למודל הבא...")
                last_error = response.text[:100]
                continue

        except Exception as e:
            last_error = str(e)
            continue

    print(f"❌ שגיאה סופית בגוגל: {last_error}")
    return "סליחה, יש לי תקלה רגעית בתקשורת. אנא נסה שוב בעוד דקה."

# ==========================================
# 📩 טיפול בהודעות
# ==========================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # 1. סינון הודעות
        if not update.message or not update.message.text: return
        # מתעלם מהודעות של הערוץ עצמו
        if update.effective_user.id == 777000: return

        user_text = update.message.text
        user_id = update.effective_user.id
        chat_type = update.effective_chat.type
        
        print(f"📩 הודעה חדשה ({chat_type}): {user_text}")

        # 2. זיהוי מספר טלפון
        phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
        match = phone_pattern.search(user_text)
        if match:
            phone = match.group(0)
            try:
                await context.bot.send_message(ADMIN_ID, f"🔔 **ליד חדש!**\n📱 `{phone}`\n💬 {user_text}", parse_mode='Markdown')
            except:
                pass 
            
            await update.message.reply_text("תודה! רשמתי את המספר, לינה תחזור אליך.")
            # ממשיכים ל-AI

        # 3. חיווי הקלדה
        if chat_type == 'private':
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

        # 4. ניהול היסטוריה
        if user_id not in chats_history: chats_history[user_id] = []
        history = ""
        for msg in chats_history[user_id][-3:]:
            history += f"{msg['role']}: {msg['text']}\n"

        # 5. שליחה לגוגל בצורה אסינכרונית (מונע תקיעות!)
        # זה התיקון הקריטי: אנחנו מריצים את הבקשה בנפרד מהבוט
        loop = asyncio.get_running_loop()
        bot_answer = await loop.run_in_executor(None, send_to_google_blocking, history, user_text)

        # 6. שליחת התשובה
        chats_history[user_id].append({"role": "user", "text": user_text})
        chats_history[user_id].append({"role": "model", "text": bot_answer})

        try:
            if chat_type == 'private':
                 await update.message.reply_text(bot_answer, reply_markup=get_main_keyboard())
            else:
                 # בקבוצה - מגיב בציטוט
                 await update.message.reply_text(bot_answer, quote=True)
        except Exception as e:
            print(f"❌ שגיאה בשליחה לטלגרם: {e}")
            await update.message.reply_text(bot_answer) # נסיון שני רגיל

    except Exception as e:
        print(f"💥 קריסה בקוד: {e}")
        traceback.print_exc()

def get_main_keyboard():
    btn = KeyboardButton("📞 שלח מספר טלפון", request_contact=True)
    return ReplyKeyboardMarkup([[btn]], resize_keyboard=True)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.message.contact
    await context.bot.send_message(ADMIN_ID, f"🔔 ליד מכפתור: {c.phone_number} ({update.effective_user.first_name})")
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
         print("\n🔴 שגיאה: המפתחות חסרים ב-Secrets! הבוט לא יעבוד. 🔴\n")
    else:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        
        app.add_handler(CommandHandler('start', start))
        app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        
        print("✅ הבוט רץ! (מושך מפתחות מ-Secrets)")
        app.run_polling()
