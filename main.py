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

MAX_MESSAGES = 3 

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==========================================
# 🧠 המוח (הנחיה חמורה לא לבקש טלפון)
# ==========================================
SYSTEM_PROMPT = """
You are the smart receptionist for 'Lina Real Estate'.
Goal: Ask clarifying questions to understand what the client needs.
RULES:
1. NEVER ask for a phone number in the first 3 turns.
2. If the user says "Rent", ask: "How many rooms and what is the budget?"
3. If the user says "Buy", ask: "Investment or living? What is the budget?"
4. Be short, professional, and Hebrew speaking.
"""

chats_history = {}
current_model_url = ""

# ==========================================
# 🔍 סורק מודלים
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
            if requests.post(url, json={"contents": [{"parts": [{"text": "."}]}]}, timeout=5).status_code == 200:
                current_model_url = url
                print(f"✅ מודל: {url}")
                return
        except: continue
    current_model_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"

find_working_model()

# ==========================================
# 🧠 שליחה ל-AI (עם הגנה מבקשת טלפון)
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
        
        # תיקון קריטי: אם גוגל נכשל, לא לבקש טלפון!
        return "רשמתי לפני. האם יש אזור מסוים בנתניה שאתה מעדיף?"
    except:
        return "אני מקשיב. כמה חדרים אתם מחפשים?"

# ==========================================
# 📩 לוגיקה
# ==========================================
def get_main_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("📞 שלח מספר לסוכן", request_contact=True)]], resize_keyboard=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    if update.effective_user.id == 777000: return

    user_text = update.message.text
    user_id = update.effective_user.id
    
    # זיהוי טלפון
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    if phone_pattern.search(user_text):
        phone = phone_pattern.search(user_text).group(0)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 ליד בטקסט!\n{phone}\n{user_text}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="תודה! הפרטים הועברו ללינה.", reply_markup=get_main_keyboard())
        return

    # היסטוריה
    if user_id not in chats_history: chats_history[user_id] = []
    
    # חיתוך לשיחה אנושית
    if len(chats_history[user_id]) >= (MAX_MESSAGES * 2):
        cut_msg = "תודה על המידע! כדי שסוכן יחזור אליך עם נכסים רלוונטיים, אנא לחץ למטה 👇"
        await context.bot.send_message(chat_id=update.effective_chat.id, text=cut_msg, reply_markup=get_main_keyboard())
        return 

    history = ""
    for msg in chats_history[user_id][-6:]: history += f"{msg['role']}: {msg['text']}\n"

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
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 ליד כפתור!\n{c.phone_number}")
    await context.bot.send_message(chat_id=update.effective_chat.id, text="תודה! הועבר לטיפול.", reply_markup=get_main_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats_history[update.effective_user.id] = []
    welcome_msg = "שלום, אני הבוט של הסוכנות Lina Real Estate בנתניה, במה אוכל לעזור לך היום?"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_msg, reply_markup=get_main_keyboard())

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    # הפקודה הזו מנקה את הבוט הישן לפני שהחדש עולה
    print("✅ מנקה בוטים כפולים...")
    app.run_polling(drop_pending_updates=True)
