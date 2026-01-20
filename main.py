import os
import requests
import logging
import re
import json
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from keep_alive import keep_alive 

# ==========================================
# ⚙️ הגדרות
# ==========================================
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_ID = 1687054059

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

SYSTEM_PROMPT = "את Lina, סוכנת נדל\"ן בנתניה. עני בעברית, קצר ומקצועי."
chats_history = {}
current_model_url = "" # נשמור כאן את המודל שעובד

# ==========================================
# 🧠 גילוי מודלים אוטומטי (Auto-Discovery)
# ==========================================
def find_working_model():
    """ שואל את גוגל איזה מודלים פתוחים ובוחר אחד """
    global current_model_url
    
    print("🔍 בודק איזה מודלים פתוחים במפתח שלך...")
    try:
        # מקבל את הרשימה האמיתית מגוגל
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        response = requests.get(list_url)
        
        if response.status_code == 200:
            data = response.json()
            if 'models' in data:
                # מחפש מודל שיודע לייצר טקסט (generateContent)
                for m in data['models']:
                    if 'generateContent' in m['supportedGenerationMethods']:
                        model_name = m['name'].replace('models/', '')
                        print(f"✅ נמצא מודל פתוח: {model_name}")
                        
                        # בונה את הכתובת המוכנה לשימוש
                        current_model_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                        return
            
            print("⚠️ לא נמצאו מודלים מתאימים ברשימה של גוגל.")
        else:
            print(f"❌ שגיאה בקבלת רשימת מודלים: {response.text}")

    except Exception as e:
        print(f"❌ שגיאת חיבור בבדיקת מודלים: {e}")

    # ברירת מחדל אם הכל נכשל - מנסים את הישן והטוב
    print("⚠️ משתמש במודל ברירת מחדל (gemini-pro)")
    current_model_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"

# מפעילים את הבדיקה מיד בהתחלה
find_working_model()

# ==========================================
# 🧠 פונקציית השליחה
# ==========================================
def send_to_google(history_text, user_text):
    if not current_model_url:
        return "שגיאת מערכת: לא נמצא מודל AI זמין."

    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nהיסטוריה:\n{history_text}\nלקוח: {user_text}\nאני:"}]
        }]
    }

    try:
        # 30 שניות timeout למניעת תקיעות
        response = requests.post(current_model_url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            error_msg = f"Google Error {response.status_code}: {response.text}"
            print(error_msg)
            return "יש לי תקלה טכנית רגעית, אשמח אם תשאיר טלפון."
            
    except Exception as e:
        print(f"Connection Error: {e}")
        return "בעיית תקשורת, נסה שוב."

# ==========================================
# 📩 הנדלרים
# ==========================================
def get_main_keyboard():
    button = KeyboardButton("📞 שלח את המספר שלי ללינה", request_contact=True)
    return ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=False)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    if update.effective_user.id == 777000: return

    user_text = update.message.text
    user_id = update.effective_user.id
    
    # היסטוריה
    if user_id not in chats_history: chats_history[user_id] = []
    history = ""
    for msg in chats_history[user_id][-4:]: history += f"{msg['role']}: {msg['text']}\n"

    if update.effective_chat.type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # שליחה לגוגל
    bot_answer = send_to_google(history, user_text)
    
    chats_history[user_id].append({"role": "user", "text": user_text})
    chats_history[user_id].append({"role": "model", "text": bot_answer})
    
    if update.effective_chat.type == 'private':
        await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer, reply_markup=get_main_keyboard())
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer, reply_to_message_id=update.message.message_id)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.message.contact
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 ליד חדש!\n{c.first_name}\n{c.phone_number}")
    except: pass
    await context.bot.send_message(chat_id=update.effective_chat.id, text="תודה! המספר נקלט.", reply_markup=get_main_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats_history[update.effective_user.id] = []
    await context.bot.send_message(chat_id=update.effective_chat.id, text="היי! אני לינה נדל\"ן 🏠", reply_markup=get_main_keyboard())

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("✅ הבוט רץ - עם מנגנון גילוי מודלים אוטומטי")
    app.run_polling()
