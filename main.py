import os
import requests
import logging
import asyncio
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from keep_alive import keep_alive

# ==========================================
# ⚙️ הגדרות
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
ADMIN_ID = 1687054059

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==========================================
# 📝 אישיות הבוט
# ==========================================
SYSTEM_PROMPT = """
You are Lina, a real estate agent in Netanya.
Language: Hebrew.
Traits: Professional, concise, inviting.
Goal: Get the client's phone number or answer property questions.
Response length: Maximum 2 sentences.
"""

# ==========================================
# 🧠 המוח של גוגל (מנגנון 4 המודלים)
# ==========================================
def ask_google_brute_force(user_text, history_text):
    """ מנסה 4 מודלים שונים עד שאחד עובד """
    
    # רשימת המודלים מהחדש לישן
    models_to_try = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-1.0-pro",
        "gemini-pro"
    ]
    
    last_error = ""

    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{
                "parts": [{"text": f"{SYSTEM_PROMPT}\n\nHistory:\n{history_text}\nUser: {user_text}\nLina:"}]
            }]
        }

        try:
            # מנסים לשלוח (עם timeout קצר של 8 שניות למודל)
            response = requests.post(url, json=payload, headers=headers, timeout=8)
            
            if response.status_code == 200:
                # יש הצלחה! מחזירים תשובה ויוצאים מהלולאה
                try:
                    return response.json()['candidates'][0]['content']['parts'][0]['text']
                except:
                    continue # מבנה לא תקין, עוברים למודל הבא
            else:
                # כישלון במודל הזה, שומרים את השגיאה וממשיכים לבא
                last_error = f"{model} Error: {response.status_code}"
                print(f"⚠️ {model} נכשל, מנסה את הבא...")
                continue

        except Exception as e:
            last_error = str(e)
            continue

    # אם יצאנו מהלולאה וכלום לא עבד:
    print(f"❌ כל המודלים נכשלו. שגיאה אחרונה: {last_error}")
    # מחזירים את השגיאה למשתמש כדי שנבין למה!
    return f"⚠️ שגיאה טכנית בחיבור לגוגל:\n{last_error}\nנא לצלם מסך זה ולשלוח לתמיכה."

# ==========================================
# 📩 טיפול בהודעות
# ==========================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    # התעלמות מערוצים
    if update.effective_user.id == 777000: return

    user_text = update.message.text
    chat_type = update.effective_chat.type
    
    # חיווי הקלדה (רק בפרטי)
    if chat_type == 'private':
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
        except: pass

    # ניהול היסטוריה
    if 'chat_history' not in context.chat_data:
        context.chat_data['chat_history'] = []
    
    recent_history = "\n".join(context.chat_data['chat_history'][-3:])

    # הרצה ברקע
    loop = asyncio.get_running_loop()
    bot_answer = await loop.run_in_executor(None, ask_google_brute_force, user_text, recent_history)

    # שמירה בהיסטוריה
    context.chat_data['chat_history'].append(f"User: {user_text}")
    context.chat_data['chat_history'].append(f"Lina: {bot_answer}")
    if len(context.chat_data['chat_history']) > 6: # שומרים רק 6 הודעות אחרונות
        context.chat_data['chat_history'] = context.chat_data['chat_history'][-6:]

    # שליחה
    try:
        if chat_type == 'private':
            await update.message.reply_text(bot_answer, reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text(bot_answer, quote=True)
    except Exception as e:
        print(f"Error sending: {e}")
        await update.message.reply_text(bot_answer)

# ==========================================
# 🎮 פקודות
# ==========================================
def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📞 שלח מספר טלפון", request_contact=True)]], 
        resize_keyboard=True
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("היי! אני לינה נדל\"ן 🏠", reply_markup=get_main_keyboard())

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.message.contact
    try:
        await context.bot.send_message(ADMIN_ID, f"🔔 ליד: {c.phone_number} ({update.effective_user.first_name})")
    except: pass
    await update.message.reply_text("תודה! רשמתי את המספר.", reply_markup=get_main_keyboard())

# ==========================================
# 🚀 הרצה
# ==========================================
if __name__ == '__main__':
    keep_alive()
    
    if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
        print("❌ חסרים מפתחות!")
    else:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler('start', start))
        app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
        
        print("✅ הבוט רץ (מצב Brute Force)")
        app.run_polling()
