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

# מספר ההודעות שהבוט יתכתב לפני שיחתוך
MAX_MESSAGES = 3 

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==========================================
# 🧠 המוח החדש (מתעניין ושואב מידע)
# ==========================================
SYSTEM_PROMPT = """
You are Lina, a professional and warm real estate agent at 'Lina Real Estate' in Netanya.
Language: Hebrew.
Tone: Engaging, professional, interested, and helpful.
Goal: Understand the client's needs (buy/rent, budget, number of rooms, area) by asking relevant questions.
Behavior:
1. In the first few messages, ASK questions to gather info. Show you care.
2. Do NOT be too short/robotic. Be conversational.
3. Do NOT write long essays. Keep it natural (2-4 sentences).
"""

chats_history = {}
current_model_url = ""

# ==========================================
# 🔍 סורק מודלים (למניעת תקלות טכניות)
# ==========================================
def find_working_model():
    global current_model_url
    possible_urls = [
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    ]
    for url in possible_urls:
        try:
            # בדיקת דופק מהירה למודל
            if requests.post(url, json={"contents": [{"parts": [{"text": "Hi"}]}]}, timeout=5).status_code == 200:
                current_model_url = url
                print(f"✅ מודל נבחר: {url}")
                return
        except: continue
    # ברירת מחדל
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
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nהיסטוריה קודמת:\n{history_text}\nלקוח: {user_text}\nאני:"}]
        }]
    }
    try:
        response = requests.post(current_model_url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        return "אני מבינה. כדי שנוכל להתקדם, אשמח למספר טלפון."
    except:
        return "יש לי בעית קליטה קטנה, אשמח אם תשאיר מספר טלפון."

# ==========================================
# 📩 לוגיקה ראשית
# ==========================================
def get_main_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("📞 שלח את המספר שלי ללינה", request_contact=True)]], resize_keyboard=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    # הגנה מלופים בערוץ
    if update.effective_user.id == 777000: return

    user_text = update.message.text
    user_id = update.effective_user.id
    
    # 1. תמיד בודקים אם יש טלפון (גם אם עברנו את המכסה)
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    if phone_pattern.search(user_text):
        phone = phone_pattern.search(user_text).group(0)
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 ליד חדש (מתוך טקסט)!\n👤 {update.effective_user.first_name}\n📱 {phone}\n📝 תוכן: {user_text}")
        except: pass
        await context.bot.send_message(chat_id=update.effective_chat.id, text="מעולה, רשמתי את הפרטים. סוכן שלנו יצור איתך קשר בהקדם! 🏠", reply_markup=get_main_keyboard())
        return

    # ניהול היסטוריה
    if user_id not in chats_history: chats_history[user_id] = []
    
    # 2. 🔥 נקודת החיתוך (אחרי 3 הודעות)
    # כל הודעה = 2 רשומות (שאלה + תשובה). אז 3 * 2 = 6.
    if len(chats_history[user_id]) >= (MAX_MESSAGES * 2):
        # הודעת הפרידה המנומסת
        cut_msg = (
            "אני רואה שיש לנו על מה לדבר! 😊\n"
            "כדי שאוכל לתת לך את השירות המקצועי ביותר ולהציע נכסים שמתאימים לך בדיוק, "
            "אשמח אם תשאיר/י מספר נייד (או ללחוץ על הכפתור למטה) "
            "וסוכן מ-Lina Real Estate יחזור אליך לשיחה אישית. 🏠"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=cut_msg, reply_markup=get_main_keyboard())
        return # עוצר כאן

    # בניית ההיסטוריה לבוט
    history = ""
    for msg in chats_history[user_id][-6:]: history += f"{msg['role']}: {msg['text']}\n"

    # חיווי הקלדה בפרטי
    if update.effective_chat.type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # שליחה לגוגל
    bot_answer = send_to_google(history, user_text)
    
    # שמירה בהיסטוריה
    chats_history[user_id].append({"role": "user", "text": user_text})
    chats_history[user_id].append({"role": "model", "text": bot_answer})
    
    # שליחת התשובה
    if update.effective_chat.type == 'private':
        await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer, reply_markup=get_main_keyboard())
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer, reply_to_message_id=update.message.message_id)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.message.contact
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 ליד חדש (כפתור)!\n👤 {c.first_name}\n📱 {c.phone_number}")
    except: pass
    await context.bot.send_message(chat_id=update.effective_chat.id, text="תודה רבה! המספר התקבל, נחזור אליך בהקדם. 🏠", reply_markup=get_main_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats_history[update.effective_user.id] = [] # איפוס מונה
    await context.bot.send_message(chat_id=update.effective_chat.id, text="היי! אני לינה מ-Lina Real Estate 🏠\nאיזה נכס מעניין אותך למצוא היום?", reply_markup=get_main_keyboard())

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("✅ הבוט רץ (הגדרה: מתעניין, חותך אחרי 3)")
    app.run_polling()
