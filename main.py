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

# הגדרת מקסימום הודעות לפני חיתוך
MAX_MESSAGES = 3 

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# החמרנו את ההנחיות לבוט כדי שיחתור למגע מהר יותר
SYSTEM_PROMPT = """
You are Lina, a real estate expert in Netanya.
Language: Hebrew.
Tone: Professional, direct, and concise.
Goal: Get the user's phone number ASAP.
Do not write long paragraphs. 
"""

chats_history = {}
current_model_url = ""

# ==========================================
# 🧠 איתור מודל גוגל (כדי למנוע 404)
# ==========================================
def find_working_model():
    global current_model_url
    possible_urls = [
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    ]
    for url in possible_urls:
        try:
            if requests.post(url, json={"contents": [{"parts": [{"text": "Hi"}]}]}, timeout=5).status_code == 200:
                current_model_url = url
                print(f"✅ מודל נבחר: {url}")
                return
        except: continue
    print("⚠️ משתמש בברירת מחדל (Pro)")
    current_model_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"

find_working_model()

# ==========================================
# 🧠 שליחה ל-AI
# ==========================================
def send_to_google(history_text, user_text):
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nהיסטוריה:\n{history_text}\nלקוח: {user_text}\nאני:"}]
        }]
    }
    try:
        response = requests.post(current_model_url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        return "אשמח אם תשאיר פרטים ואחזור אליך."
    except:
        return "יש לי בעית קליטה, אשמח למספר טלפון."

# ==========================================
# 📩 לוגיקה ראשית
# ==========================================
def get_main_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("📞 שלח את המספר שלי ללינה", request_contact=True)]], resize_keyboard=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    if update.effective_user.id == 777000: return

    user_text = update.message.text
    user_id = update.effective_user.id
    
    # 1. בדיקה אם יש מספר טלפון בהודעה (תמיד עובד, גם אם עברנו את המכסה)
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    if phone_pattern.search(user_text):
        phone = phone_pattern.search(user_text).group(0)
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 ליד חדש (מתוך טקסט)!\n👤 {update.effective_user.first_name}\n📱 {phone}")
        except: pass
        await context.bot.send_message(chat_id=update.effective_chat.id, text="מעולה, רשמתי את המספר. אחזור אליך בהקדם! 🏠", reply_markup=get_main_keyboard())
        return

    # ניהול היסטוריה
    if user_id not in chats_history: chats_history[user_id] = []
    
    # 2. 🔥 ה"סכין": בדיקה אם עברנו את כמות ההודעות המותרת
    # כל אינטראקציה מוסיפה 2 רשומות (משתמש + בוט). אז 3 הודעות = 6 רשומות.
    if len(chats_history[user_id]) >= (MAX_MESSAGES * 2):
        cut_msg = "הבנתי, יש לנו על מה לדבר. כדי שנתקדם ברצינות, אנא השאר מספר נייד (או לחץ על הכפתור למטה) ואחזור אליך לשיחה מסודרת. 👇"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=cut_msg, reply_markup=get_main_keyboard())
        return # 🛑 עוצר כאן! לא שולח לגוגל יותר.

    # המשך רגיל (אם לא עברנו את המכסה)
    history = ""
    for msg in chats_history[user_id][-4:]: history += f"{msg['role']}: {msg['text']}\n"

    if update.effective_chat.type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
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
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 ליד חדש (כפתור)!\n👤 {c.first_name}\n📱 {c.phone_number}")
    except: pass
    await context.bot.send_message(chat_id=update.effective_chat.id, text="תודה! המספר נקלט.", reply_markup=get_main_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats_history[update.effective_user.id] = [] # איפוס מונה בהתחלה
    await context.bot.send_message(chat_id=update.effective_chat.id, text="היי! אני לינה נדל\"ן 🏠\nאיך אפשר לעזור?", reply_markup=get_main_keyboard())

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("✅ הבוט רץ (מוגבל ל-3 הודעות שיחה)")
    app.run_polling()
