import os
import requests
import time
import logging
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from keep_alive import keep_alive

# ==========================================
# ⚙️ הגדרות (Settings)
# ==========================================

# תיקון קריטי: המספר 1687054059 הוא מזהה משתמש (User ID).
# לא מוסיפים לו -100 (זה רק לערוצים). ככה הבוט ישלח הודעה ישירות אליך.
ADMIN_ID = 1687054059

PROMPT_FILE_NAME = "prompt_realtor.txt"
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

# בדיקה שהמפתחות קיימים
if not GEMINI_API_KEY or not TELEGRAM_BOT_TOKEN:
    raise SystemExit("❌ שגיאה: מפתחות (Secrets) חסרים! נא להגדיר GEMINI_API_KEY ו-TELEGRAM_BOT_TOKEN.")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# טעינת קובץ ההוראות
try:
    with open(PROMPT_FILE_NAME, 'r', encoding='utf-8') as file:
        SYSTEM_PROMPT = file.read()
except FileNotFoundError:
    SYSTEM_PROMPT = "You are a helpful real estate assistant."
    print(f"⚠️ הערה: הקובץ {PROMPT_FILE_NAME} לא נמצא. משתמש בהוראות ברירת מחדל.")

chats_history = {}

# ==========================================
# 🧠 פונקציות ליבה (Core Logic)
# ==========================================

def send_to_google_direct(history_text, user_text):
    """ שולח בקשה לגוגל דרך HTTP ישיר """
    models_to_try = [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ]
    
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nהיסטוריה:\n{history_text}\nלקוח: {user_text}\nאני:"}]
        }]
    }

    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        try:
            response = requests.post(url, json=payload, headers=headers)
            if response.status_code == 200:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            elif response.status_code == 429:
                time.sleep(1)
                continue
            else:
                continue
        except Exception as e:
            print(f"Error connecting to {model_name}: {e}")
            continue
            
    return None

async def send_lead_alert(context: ContextTypes.DEFAULT_TYPE, name, username, phone, source_text=""):
    """ פונקציית עזר לשליחת ההתראה למנהל """
    alert_text = (
        f"🔔 <b>ליד חדש התקבל!</b>\n"
        f"➖➖➖➖➖➖➖\n"
        f"👤 <b>שם:</b> {name}\n"
        f"🔗 <b>יוזר:</b> @{username if username else 'אין'}\n"
        f"📱 <b>טלפון:</b> {phone}\n"
        f"📝 <b>תוכן/מקור:</b> {source_text}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=alert_text, parse_mode='HTML')
        print(f"✅ ליד נשלח בהצלחה ל-ID: {ADMIN_ID}")
    except Exception as e:
        print(f"❌ שגיאה בשליחה למנהל: {e}")

# --- פונקציה חדשה: מטפלת בכרטיס איש קשר (הכפתור) ---
async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ מטפל במי ששלח את המספר דרך כפתור שיתוף """
    contact = update.message.contact
    user_name = update.effective_user.first_name
    username = update.effective_user.username
    phone_number = contact.phone_number

    print(f"📞 התקבל איש קשר: {phone_number}")

    # 1. שליחת התראה ללינה
    await send_lead_alert(context, user_name, username, phone_number, source_text="שיתוף איש קשר")

    # 2. תגובה ללקוח
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="תודה רבה! המספר התקבל בהצלחה. לינה תחזור אליך בהקדם."
    )

async def check_for_lead_in_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ בודק אם המשתמש הקליד מספר טלפון ידנית בטקסט """
    user_text = update.message.text
    user_name = update.effective_user.first_name
    username = update.effective_user.username
    
    # חיפוש טלפון בטקסט
    phone_pattern = re.compile(r'\b0?5[0-9]{8}\b') 
    clean_text = user_text.replace("-", "").replace(" ", "")
    match = phone_pattern.search(clean_text)
    
    if match:
        found_phone = match.group(0)
        print(f"📞 זוהה טלפון בטקסט: {found_phone}")
        await send_lead_alert(context, user_name, username, found_phone, source_text=user_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    
    # 1. בדיקה אם הוקלד טלפון בתוך הטקסט
    await check_for_lead_in_text(update, context)

    # 2. ניהול שיחה רגילה
    if user_id not in chats_history:
        chats_history[user_id] = []

    history_txt = ""
    for msg in chats_history[user_id][-6:]:
        history_txt += f"{msg['role']}: {msg['text']}\n"

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    bot_answer = send_to_google_direct(history_txt, user_text)
    
    if not bot_answer:
        bot_answer = "מצטער, אני בודק משהו במערכת. תוכל לנסות שוב בעוד רגע?"

    chats_history[user_id].append({"role": "לקוח", "text": user_text})
    chats_history[user_id].append({"role": "אני", "text": bot_answer})
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats_history[update.effective_user.id] = []
    welcome_msg = "שלום! אני העוזרת הדיגיטלית של לינה נדל\"ן. איך אפשר לעזור?"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_msg)

if __name__ == '__main__':
    print("🧹 מנקה חיבורים ישנים...")
    try:
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=True")
    except Exception:
        pass

    keep_alive()

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # --- הוספת המאזינים (Handlers) ---
    application.add_handler(CommandHandler('start', start))
    
    # קריטי: מאזין מיוחד לאנשי קשר (Contact)
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    
    # מאזין לטקסט רגיל
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print(f"🚀 הבוט רץ! התראות יישלחו למספר: {ADMIN_ID}")
    application.run_polling()
