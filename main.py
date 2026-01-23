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

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==========================================
# 🧠 ניהול זיכרון שלבים (State Machine)
# ==========================================
# המילון הזה ישמור לכל משתמש באיזה שלב הוא נמצא
# 0 = התחלה
# 1 = שאלנו "קניה או השכרה?", מחכים לתשובה
# 2 = שאלנו "תקציב וחדרים?", מחכים לתשובה
# 3 = שאלנו "אזור?", מחכים לתשובה
# 4 = סיימנו, מבקשים רק טלפון
user_states = {}
chats_history = {} # שומרים היסטוריה רק בשביל הקונטקסט ל-AI

# כתובות AI
current_model_url = ""

def find_working_model():
    global current_model_url
    possible_urls = [
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    ]
    for url in possible_urls:
        try:
            if requests.post(url, json={"contents": [{"parts": [{"text": "."}]}]}, timeout=5).status_code == 200:
                current_model_url = url
                return
        except: continue
    current_model_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"

find_working_model()

# ==========================================
# 🧠 יצירת תשובה חכמה לפי השלב
# ==========================================
def generate_response(user_text, state, history_text):
    
    # הנחיות מדויקות ל-AI לפי השלב בו המשתמש נמצא
    prompt_instruction = ""
    
    if state == 1:
        # המשתמש ענה עכשיו על קניה/השכרה. הבוט צריך לשאול על חדרים ותקציב.
        prompt_instruction = "The user said Buy/Rent. Reply nicely and ASK: 'How many rooms and what is the budget?'"
    elif state == 2:
        # המשתמש ענה על תקציב. הבוט צריך לשאול על אזור.
        prompt_instruction = "The user gave budget/rooms. Reply nicely and ASK: 'Do you have a preferred area in Netanya?'"
    elif state == 3:
        # המשתמש ענה על אזור. הבוט צריך לסיים.
        prompt_instruction = "The user gave area. Say thank you and that you are checking availability."

    system_prompt = f"""
    You are the receptionist for Lina Real Estate.
    Language: Hebrew.
    Current Goal: {prompt_instruction}
    Keep it short (1-2 sentences).
    NEVER ask for a phone number yet.
    """

    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{system_prompt}\n\nהיסטוריה:\n{history_text}\nלקוח: {user_text}\nאני:"}]
        }]
    }
    
    try:
        response = requests.post(current_model_url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
    except: pass
    
    # גיבוי ידני אם ה-AI נכשל (כדי שהרצף לא יישבר)
    if state == 1: return "מעולה. כמה חדרים אתם מחפשים ומה התקציב בערך?"
    if state == 2: return "רשמתי. יש אזור מסוים בנתניה שאתם מעדיפים?"
    return "תודה על הפרטים."

# ==========================================
# 📩 לוגיקה ראשית
# ==========================================
def get_main_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("📞 לחץ כאן להשארת מספר לסוכן", request_contact=True)]], resize_keyboard=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    if update.effective_user.id == 777000: return

    user_text = update.message.text
    user_id = update.effective_user.id
    
    # 1. בדיקת טלפון (עוקף הכל)
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    if phone_pattern.search(user_text):
        phone = phone_pattern.search(user_text).group(0)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 ליד בטקסט!\n{phone}\n{user_text}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="תודה! המספר נשמר ויועבר ללינה. 🏠", reply_markup=get_main_keyboard())
        # מסיימים את השיחה
        user_states[user_id] = 4 
        return

    # 2. ניהול שלבים (State Machine)
    # ברירת מחדל: אם המשתמש לא קיים, הוא בשלב 0
    current_state = user_states.get(user_id, 0)

    # אם המשתמש כבר סיים את התהליך (שלב 4), לא נמשיך לשוחח איתו
    if current_state >= 4:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="כדי שנתקדם, אנא לחץ על הכפתור למטה להשארת מספר 👇", reply_markup=get_main_keyboard())
        return

    # קידום השלב!
    # המשתמש שלח הודעה -> אנחנו מניחים שהוא ענה על השאלה הקודמת -> מתקדמים לשלב הבא
    next_state = current_state + 1
    user_states[user_id] = next_state # שומרים את השלב החדש

    # בדיקה: האם הגענו לסוף? (אחרי שענה על אזור)
    if next_state == 4:
        final_msg = (
            "תודה רבה! יש לי את כל המידע שצריך. 🏠\n"
            "כדי שסוכן אנושי יחזור אליך עם נכסים רלוונטיים בול למה שביקשת, "
            "אנא לחץ על הכפתור למטה להשארת נייד."
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=final_msg, reply_markup=get_main_keyboard())
        return

    # הכנת ההיסטוריה ל-AI
    if user_id not in chats_history: chats_history[user_id] = []
    history_str = ""
    for msg in chats_history[user_id][-4:]: history_str += f"{msg['role']}: {msg['text']}\n"

    # חיווי הקלדה
    if update.effective_chat.type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    # שליחה ל-AI עם השלב *החדש* שאנחנו נמצאים בו
    # אנחנו שולחים את next_state כי זה השלב שאנחנו רוצים שהבוט *ישאל* עליו עכשיו
    bot_answer = generate_response(user_text, next_state, history_str)

    # שמירה ועדכון
    chats_history[user_id].append({"role": "user", "text": user_text})
    chats_history[user_id].append({"role": "model", "text": bot_answer})

    await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer, reply_markup=get_main_keyboard())

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.message.contact
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 ליד כפתור!\n{c.phone_number}\n{c.first_name}")
    await context.bot.send_message(chat_id=update.effective_chat.id, text="קיבלתי! סוכן שלנו יחייג אליך בהקדם. 🏠", reply_markup=get_main_keyboard())
    # נועלים את המשתמש בסוף
    user_states[update.effective_user.id] = 4

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # איפוס מוחלט להתחלה
    user_states[user_id] = 0 
    chats_history[user_id] = []
    
    welcome_msg = "שלום, אני הבוט של הסוכנות Lina Real Estate בנתניה 🏠\nבמה אוכל לעזור לך היום? (קנייה או השכרה?)"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_msg, reply_markup=get_main_keyboard())

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("✅ הבוט הליניארי רץ (אין חזרות לאחור)")
    app.run_polling(drop_pending_updates=True)
