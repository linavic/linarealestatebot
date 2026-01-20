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

# 1. מפתחות - הבוט ינסה לקחת מההגדרות, ואם אין - יתריע
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
ADMIN_ID = 1687054059  # ה-ID שלך לקבלת הלידים

if not GEMINI_API_KEY or not TELEGRAM_BOT_TOKEN:
    print("❌ שגיאה קריטית: חסרים מפתחות! נא להגדיר GEMINI_API_KEY ו-TELEGRAM_BOT_TOKEN.")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# 2. טעינת הנחיות (Prompt)
try:
    with open("prompt_realtor.txt", 'r', encoding='utf-8') as file:
        SYSTEM_PROMPT = file.read()
except FileNotFoundError:
    SYSTEM_PROMPT = "You are a helpful real estate assistant named Lina."

# הוספת הנחיה שתגרום לבוט להיות קצר כשהוא בקבוצה
SYSTEM_PROMPT += "\n\nהנחיה חשובה: אם השיחה מתבצעת בקבוצה/ערוץ, היה קצר, ענייני, ומקצועי. אל תכתוב תשובות ארוכות מדי."

chats_history = {}

# ==========================================
# 🧠 מוח - חיבור לגוגל (AI)
# ==========================================

def get_main_keyboard():
    """ כפתור לשיתוף טלפון (עובד רק בפרטי) """
    button = KeyboardButton("📞 שלח את המספר שלי ללינה", request_contact=True)
    return ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=False)

def send_to_google_direct(history_text, user_text):
    """ שולח לגוגל ומחזיר את התשובה או את השגיאה אם נכשל """
    
    # שימוש במודל 1.5 פלאש - הכי מהיר ויציב לבוטים
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
        
        # בדיקה אם התשובה תקינה (קוד 200)
        if response.status_code == 200:
            try:
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            except KeyError:
                return "⚠️ שגיאה: גוגל החזיר תשובה ריקה (מסוננת)."
        
        # אם יש שגיאה - מחזירים אותה כדי שנראה בטלגרם מה הבעיה
        else:
            error_msg = f"⚠️ תקלה בגוגל (קוד {response.status_code}):\n{response.text[:150]}"
            print(error_msg)
            return error_msg

    except Exception as e:
        return f"⚠️ שגיאת חיבור חמורה:\n{str(e)}"

# ==========================================
# 📩 ניהול הודעות
# ==========================================

async def send_lead_alert(context, name, username, phone, source):
    """ שולח התראה למנהל (אליך) """
    msg = (
        f"🔔 <b>ליד חדש!</b>\n"
        f"👤 {name} (@{username if username else 'אין'})\n"
        f"📱 {phone}\n"
        f"📝 {source}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode='HTML')
    except Exception as e:
        print(f"❌ שגיאה בשליחת התראה למנהל: {e}")

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ לחיצה על כפתור שיתוף מספר """
    c = update.message.contact
    await send_lead_alert(context, update.effective_user.first_name, update.effective_user.username, c.phone_number, "כפתור שיתוף")
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="תודה רבה! המספר נקלט אצל לינה.",
        reply_markup=get_main_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ הפונקציה הראשית שמטפלת בכל הודעה """
    
    # סינונים והגנות
    if not update.message or not update.message.text: return
    # התעלמות מהודעות מערכת של הערוץ עצמו (ID 777000)
    if update.effective_user.id == 777000: return

    user_text = update.message.text
    chat_type = update.effective_chat.type # private / group / supergroup

    # 1. חיפוש מספר טלפון בטקסט
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    match = phone_pattern.search(user_text)

    if match:
        phone = match.group(0)
        # שליחת התראה
        await send_lead_alert(context, update.effective_user.first_name, update.effective_user.username, phone, f"זוהה בשיחה ({chat_type}): {user_text}")
        
        # תגובה ללקוח
        reply = "תודה! רשמתי את המספר, לינה תחזור אליך."
        if chat_type == 'private':
            await update.message.reply_text(reply, reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text(reply)
        
        # ממשיכים ל-AI למקרה שיש גם שאלה

    # 2. שליחה ל-AI
    # חיווי הקלדה (רק בפרטי כדי לא להציק בקבוצה)
    if chat_type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    # ניהול היסטוריה
    user_id = update.effective_user.id
    if user_id not in chats_history: chats_history[user_id] = []
    
    history = ""
    for msg in chats_history[user_id][-3:]:
        history += f"{msg['role']}: {msg['text']}\n"

    # --- קריאה לפונקציה (שעכשיו מחזירה שגיאות אם יש) ---
    bot_answer = send_to_google_direct(history, user_text)

    # שמירה בהיסטוריה
    chats_history[user_id].append({"role": "user", "text": user_text})
    chats_history[user_id].append({"role": "model", "text": bot_answer})

    # שליחת התשובה לטלגרם
    try:
        if chat_type == 'private':
            await update.message.reply_text(bot_answer, reply_markup=get_main_keyboard())
        else:
            # בקבוצה - עונים כ-Reply להודעה הספציפית
            await update.message.reply_text(bot_answer)
            
    except Exception as e:
        print(f"❌ שגיאה בשליחת הודעה לטלגרם: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats_history[update.effective_user.id] = []
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="שלום! אני הבוט של לינה נדל\"ן 🏠\nאיך אני יכולה לעזור?", 
        reply_markup=get_main_keyboard()
    )

# ==========================================
# 🚀 הרצה
# ==========================================

if __name__ == '__main__':
    keep_alive() # שרת Flask כדי להישאר באוויר
    
    # ניקוי Webhooks ישנים
    try:
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook?drop_pending_updates=True")
    except:
        pass

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print(f"✅ הבוט מחובר! לידים יישלחו ל-ID: {ADMIN_ID}")
    app.run_polling()
