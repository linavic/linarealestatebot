import os
import requests
import time
import logging
import re
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from keep_alive import keep_alive

# ==========================================
# ⚙️ הגדרות (Settings)
# ==========================================

ADMIN_ID = 1687054059  # המספר שלך לקבלת לידים

PROMPT_FILE_NAME = "prompt_realtor.txt"
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

if not GEMINI_API_KEY or not TELEGRAM_BOT_TOKEN:
    raise SystemExit("❌ שגיאה: מפתחות חסרים!")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# טעינת הוראות
try:
    with open(PROMPT_FILE_NAME, 'r', encoding='utf-8') as file:
        SYSTEM_PROMPT = file.read()
except FileNotFoundError:
    SYSTEM_PROMPT = "You are a helpful real estate assistant."

chats_history = {}

# ==========================================
# 🧠 פונקציות עזר (AI + מקלדת)
# ==========================================

def get_main_keyboard():
    """ יצירת כפתור בולט לשליחת מספר """
    button = KeyboardButton("📞 שלח את המספר שלי ללינה", request_contact=True)
    # resize_keyboard=True עושה שהכפתור לא יהיה ענק
    return ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=False)

def send_to_google_direct(history_text, user_text):
    """ שליחה ל-Gemini 1.5 Flash (הכי יציב) """
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
            print(f"❌ שגיאה מגוגל: {response.text}")
            return None
    except Exception as e:
        print(f"❌ שגיאת תקשורת: {e}")
        return None

# ==========================================
# 📩 טיפול בלידים והודעות
# ==========================================

async def send_lead_alert(context: ContextTypes.DEFAULT_TYPE, name, username, phone, source_text=""):
    """ שולח התראה ללינה """
    alert_text = (
        f"🔔 <b>ליד חדש נכנס!</b>\n"
        f"➖➖➖➖➖➖➖\n"
        f"👤 <b>שם:</b> {name}\n"
        f"🔗 <b>יוזר:</b> @{username if username else 'אין'}\n"
        f"📱 <b>טלפון:</b> {phone}\n"
        f"📝 <b>הקשר:</b> {source_text}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=alert_text, parse_mode='HTML')
    except Exception as e:
        print(f"❌ שגיאה בשליחה למנהל: {e}")

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ מטפל בלחיצה על הכפתור 'שלח מספר' """
    contact = update.message.contact
    user_name = update.effective_user.first_name
    
    # 1. שליחת התראה ללינה
    await send_lead_alert(
        context, 
        user_name, 
        update.effective_user.username, 
        contact.phone_number, 
        "נשלח דרך כפתור שיתוף"
    )
    
    # 2. תגובה ללקוח (משאירים את הכפתור למקרה שיצטרך שוב)
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=f"תודה {user_name}! המספר {contact.phone_number} התקבל אצל לינה. נחזור אליך בהקדם.",
        reply_markup=get_main_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    if not user_text: return # הגנה מהודעות ריקות

    # --- שלב 1: בדיקת מספר טלפון בתוך הטקסט (Regex משופר) ---
    # תומך ב: 0541234567, 054-1234567, 054 1234567
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    match = phone_pattern.search(user_text)

    if match:
        found_phone = match.group(0)
        print(f"📞 זוהה טלפון בטקסט: {found_phone}")
        
        # שליחת התראה ללינה
        await send_lead_alert(context, user_name, update.effective_user.username, found_phone, f"זוהה בטקסט: {user_text}")
        
        # הודעה ללקוח שקלטנו את המספר
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="תודה! רשמתי את המספר שלך ולינה תיצור קשר.",
            reply_markup=get_main_keyboard()
        )
        # אופציונלי: כאן אפשר לעצור (return) או לתת ל-AI להמשיך לענות.
        # כרגע נמשיך כדי שהבוט יענה גם על שאלות אחרות אם היו באותה הודעה.

    # --- שלב 2: שיחה עם ה-AI ---
    
    # ניהול היסטוריה
    if user_id not in chats_history:
        chats_history[user_id] = []

    history_txt = ""
    for msg in chats_history[user_id][-6:]:
        history_txt += f"{msg['role']}: {msg['text']}\n"

    # חיווי הקלדה
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # שליחה לגוגל
    bot_answer = send_to_google_direct(history_txt, user_text)
    
    if not bot_answer:
        # במקרה של תקלה ב-AI, עונים הודעה גנרית אבל לא "שגיאה"
        bot_answer = "קיבלתי את ההודעה. אם זה דחוף, אנא השתמש בכפתור למטה לשיתוף הטלפון."

    # עדכון היסטוריה
    chats_history[user_id].append({"role": "user", "text": user_text})
    chats_history[user_id].append({"role": "model", "text": bot_answer})
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=bot_answer,
        reply_markup=get_main_keyboard() # תמיד מוודאים שהכפתור קיים
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats_history[update.effective_user.id] = []
    welcome_msg = (
        "שלום! אני העוזרת הדיגיטלית של לינה נדל\"ן 🏠\n"
        "איך אפשר לעזור לך היום?\n\n"
        "👇 **למענה מהיר, ניתן ללחוץ על הכפתור למטה לשיתוף טלפון**"
    )
    # כאן אנחנו שולחים את המקלדת בפעם הראשונה
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=welcome_msg, 
        reply_markup=get_main_keyboard()
    )

# ==========================================
# 🚀 הרצה
# ==========================================

if __name__ == '__main__':
    keep_alive()
    
    try:
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=True")
    except:
        pass

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print(f"✅ הבוט מחובר! התראות יישלחו ל: {ADMIN_ID}")
    app.run_polling()
