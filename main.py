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

# מפתחות (נלקחים מהסביבה או שמים ידנית לבדיקה)
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_ID = 1687054059  # ה-ID שלך לקבלת לידים

# בדיקה קריטית
if not GEMINI_API_KEY or not TELEGRAM_BOT_TOKEN:
    raise SystemExit("❌ שגיאה: חסרים מפתחות (API Key או Token). בדוק את ה-Secrets שלך.")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# טעינת קובץ הנחיות לבוט
try:
    with open("prompt_realtor.txt", 'r', encoding='utf-8') as file:
        SYSTEM_PROMPT = file.read()
except FileNotFoundError:
    SYSTEM_PROMPT = "You are a helpful real estate assistant named Lina."

# הוספת הנחיה ספציפית לעבודה בקבוצות
SYSTEM_PROMPT += "\n\nהנחיה חשובה: אם אתה עונה בתוך קבוצה פומבית, היה קצר, ענייני, ומקצועי. אל תאריך יותר מדי."

chats_history = {}

# ==========================================
# 🧠 מוח (Gemini AI)
# ==========================================

def get_main_keyboard():
    """ יצירת הכפתור לשיתוף טלפון (מופיע רק בפרטי) """
    button = KeyboardButton("📞 שלח את המספר שלי ללינה", request_contact=True)
    return ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=False)

def send_to_google_direct(history_text, user_text):
    """ שליחה למודל היציב gemini-1.5-flash """
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
            print(f"⚠️ שגיאה מגוגל: {response.text}")
            return None
    except Exception as e:
        print(f"❌ שגיאת חיבור: {e}")
        return None

# ==========================================
# 📩 ניהול הודעות ולידים
# ==========================================

async def send_lead_alert(context, name, username, phone, source):
    """ שולח התראה למנהל (Lina) """
    msg = (
        f"🔔 <b>ליד חדש נכנס!</b>\n"
        f"➖➖➖➖➖➖➖\n"
        f"👤 <b>שם:</b> {name}\n"
        f"🔗 <b>יוזר:</b> @{username if username else 'אין'}\n"
        f"📱 <b>טלפון:</b> {phone}\n"
        f"📝 <b>מקור:</b> {source}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode='HTML')
    except Exception as e:
        print(f"❌ לא הצלחתי לשלוח התראה למנהל: {e}")

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ מטפל בלחיצה על כפתור שיתוף טלפון """
    c = update.message.contact
    await send_lead_alert(context, update.effective_user.first_name, update.effective_user.username, c.phone_number, "כפתור שיתוף (פרטי)")
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="תודה רבה! המספר שלך התקבל אצל לינה. נחזור אליך בהקדם.",
        reply_markup=get_main_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # הגנות: אם אין הודעה, אין טקסט, או שזה עדכון מערכת
    if not update.message or not update.message.text:
        return

    # === סינון קריטי לערוצים ===
    # ID 777000 הוא המשתמש של טלגרם שמעביר פוסטים מהערוץ לקבוצה.
    # אנחנו לא רוצים שהבוט יענה לפוסטים של עצמו, אלא רק לאנשים שמגיבים.
    if update.effective_user.id == 777000:
        return

    user_text = update.message.text
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type  # 'private', 'group', 'supergroup'

    # 1. זיהוי מספר טלפון בתוך הטקסט (Regex)
    # תומך בפורמטים: 0541234567, 054-1234567, 054 1234567
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    match = phone_pattern.search(user_text)

    if match:
        phone = match.group(0)
        source_info = f"זוהה בשיחה ({chat_type}): {user_text}"
        
        # שליחת הליד ללינה
        await send_lead_alert(context, update.effective_user.first_name, update.effective_user.username, phone, source_info)
        
        # תגובה ללקוח
        reply_txt = "תודה! רשמתי את המספר, לינה תחזור אליך."
        if chat_type == 'private':
            await update.message.reply_text(reply_txt, reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text(reply_txt)
        
        # לא עוצרים כאן (return), אלא נותנים לבוט להמשיך לענות אם נשאלה שאלה בנוסף למספר

    # 2. ניהול שיחה עם AI
    if user_id not in chats_history:
        chats_history[user_id] = []

    # בניית היסטוריה (3 הודעות אחרונות כדי לא להעמיס)
    history = ""
    for msg in chats_history[user_id][-3:]:
        history += f"{msg['role']}: {msg['text']}\n"

    # חיווי הקלדה (רק בפרטי, כדי לא להציק בקבוצה)
    if chat_type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # שליחה לגוגל
    bot_answer = send_to_google_direct(history, user_text)
    
    if bot_answer:
        # שמירת היסטוריה
        chats_history[user_id].append({"role": "user", "text": user_text})
        chats_history[user_id].append({"role": "model", "text": bot_answer})
        
        # שליחת התשובה
        if chat_type == 'private':
            # בפרטי: שולחים עם המקלדת הקבועה
            await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer, reply_markup=get_main_keyboard())
        else:
            # בקבוצה/ערוץ: עונים ב-Reply להודעה הספציפית
            await update.message.reply_text(bot_answer)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats_history[update.effective_user.id] = []
    welcome_text = "שלום! אני העוזרת הדיגיטלית של לינה נדל\"ן 🏠\nמוזמנים לשאול אותי כל שאלה, או להשאיר מספר טלפון."
    await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_text, reply_markup=get_main_keyboard())

# ==========================================
# 🚀 הרצה (Main Loop)
# ==========================================

if __name__ == '__main__':
    # שרת שמשאיר את הבוט חי
    keep_alive()
    
    # ניקוי Webhook ישן (מונע התנגשויות)
    try:
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=True")
    except:
        pass

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # חיבור הפונקציות לאירועים
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact)) # טיפול בכפתור שיתוף
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message)) # טיפול בטקסט (פרטי + קבוצות)
    
    print(f"✅ הבוט של לינה מחובר ומוכן לעבודה! (Admin ID: {ADMIN_ID})")
    app.run_polling()
