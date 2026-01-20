import os
import requests
import time
import logging
import re
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from keep_alive import keep_alive

# ==========================================
# 🛑 עריכה נדרשת: שים כאן את המפתח שלך
# ==========================================

# שים את המפתח שלך בתוך הגרשיים במקום ה-XXX
GEMINI_API_KEY = "XXX_PASTE_YOUR_GOOGLE_API_KEY_HERE_XXX" 

# את הטוקן של הטלגרם נשאיר כמו שהוא (או שתדביק גם אותו אם צריך)
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_ID = 1687054059

# ==========================================
# ⚙️ בדיקות מקדימות
# ==========================================

if "XXX_" in GEMINI_API_KEY:
    print("⚠️ שים לב! לא החלפת את ה-API KEY בקוד.")

if not TELEGRAM_BOT_TOKEN:
    raise SystemExit("❌ שגיאה: חסר טוקן טלגרם (TELEGRAM_BOT_TOKEN).")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

try:
    with open("prompt_realtor.txt", 'r', encoding='utf-8') as file:
        SYSTEM_PROMPT = file.read()
except FileNotFoundError:
    SYSTEM_PROMPT = "You are a helpful real estate assistant."

chats_history = {}

# ==========================================
# 🧠 חיבור לגוגל (עם חשיפת שגיאות)
# ==========================================

def get_main_keyboard():
    button = KeyboardButton("📞 שלח את המספר שלי ללינה", request_contact=True)
    return ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=False)

def send_to_google_direct(history_text, user_text):
    """ שולח לגוגל, ואם נכשל - מחזיר את סיבת הכישלון """
    
    # שימוש במודל הרגיל והיציב
    model_name = "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nהיסטוריה:\n{history_text}\nלקוח: {user_text}\nאני:"}]
        }]
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            # במקום להחזיר None, נחזיר את השגיאה האמיתית כדי שתראה אותה בטלגרם
            error_msg = response.text
            print(f"❌ שגיאה מגוגל: {error_msg}")
            return f"⚠️ שגיאה טכנית בגוגל (קוד {response.status_code}):\n{error_msg[:200]}..." # מקצר את השגיאה
            
    except Exception as e:
        return f"⚠️ שגיאת תקשורת חמורה:\n{str(e)}"

# ==========================================
# 📩 הנדלרים (אותו דבר כמו קודם)
# ==========================================

async def send_lead_alert(context, name, username, phone, source):
    msg = f"🔔 <b>ליד חדש!</b>\n👤 {name}\n📱 {phone}\n📝 {source}"
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode='HTML')
    except:
        pass

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.message.contact
    await send_lead_alert(context, update.effective_user.first_name, update.effective_user.username, c.phone_number, "כפתור שיתוף")
    await context.bot.send_message(chat_id=update.effective_chat.id, text="תודה! המספר נקלט.", reply_markup=get_main_keyboard())

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    
    # זיהוי טלפון בטקסט
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    if phone_pattern.search(user_text):
        phone = phone_pattern.search(user_text).group(0)
        await send_lead_alert(context, update.effective_user.first_name, update.effective_user.username, phone, f"טקסט: {user_text}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="רשמתי את המספר, תודה!", reply_markup=get_main_keyboard())

    # היסטוריה ו-AI
    if user_id not in chats_history: chats_history[user_id] = []
    
    history = ""
    for msg in chats_history[user_id][-4:]: history += f"{msg['role']}: {msg['text']}\n"

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # שליחה לגוגל - עכשיו זה יחזיר תשובה או את השגיאה המפורטת
    bot_answer = send_to_google_direct(history, user_text)
    
    chats_history[user_id].append({"role": "user", "text": user_text})
    chats_history[user_id].append({"role": "model", "text": bot_answer})
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer, reply_markup=get_main_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats_history[update.effective_user.id] = []
    await context.bot.send_message(chat_id=update.effective_chat.id, text="שלום! אני הבוט של לינה.", reply_markup=get_main_keyboard())

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.run_polling()
