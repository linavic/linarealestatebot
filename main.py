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

# מספר שאלות שהבוט ישאל לפני שיעביר לסוכן
MAX_MESSAGES = 3 

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==========================================
# 🧠 המוח החדש (הוראות בעברית למניעת בלבול)
# ==========================================
SYSTEM_PROMPT = """
התפקיד שלך: את המזכירה החכמה של סוכנות הנדל"ן "Lina Real Estate" בנתניה.
המטרה: לסנן את הלקוח ולהבין מה הוא מחפש לפני שמעבירים אותו לסוכן.

הוראות התנהגות קריטיות:
1. אל תבקשי מספר טלפון אף פעם. המערכת תעשה את זה בסוף.
2. תשאלי שאלות קצרות וממוקדות (אחת בכל פעם).
3. אם הלקוח אומר "היי", תשאלי: "האם את/ה מחפש/ת לקנות או לשכור?"
4. אם הלקוח אמר "לשכור" או "לקנות", תשאלי: "באיזה תקציב וכמה חדרים?"
5. אם הלקוח ענה, תשאלי: "יש אזור ספציפי בנתניה שמעניין אותך?"
6. תהיי נחמדה, מקצועית ועניינית.
"""

chats_history = {}
current_model_url = ""

# ==========================================
# 🔍 סורק מודלים (למניעת תקלות)
# ==========================================
def find_working_model():
    global current_model_url
    # מנסה למצוא את המודל הכי יציב
    possible_urls = [
        f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}",
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    ]
    for url in possible_urls:
        try:
            if requests.post(url, json={"contents": [{"parts": [{"text": "Hi"}]}]}, timeout=5).status_code == 200:
                current_model_url = url
                print(f"✅ מודל נבחר: {url}")
                return
        except: continue
    
    # ברירת מחדל
    current_model_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"

find_working_model()

# ==========================================
# 🧠 שליחה ל-AI
# ==========================================
def send_to_google(history_text, user_text):
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nהיסטוריה קודמת:\n{history_text}\nלקוח: {user_text}\nאני (המזכירה):"}]
        }]
    }
    try:
        response = requests.post(current_model_url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            # תיקון קריטי: אם יש שגיאה, לא לבקש טלפון ישר!
            return "לא הבנתי בדיוק, תוכל לפרט שוב?"
    except:
        return "יש לי הפרעה קטנה בקליטה, אפשר לחזור על המשפט?"

# ==========================================
# 📩 לוגיקה ראשית
# ==========================================
def get_main_keyboard():
    return ReplyKeyboardMarkup([[KeyboardButton("📞 שלח מספר לסוכן", request_contact=True)]], resize_keyboard=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    if update.effective_user.id == 777000: return

    user_text = update.message.text
    user_id = update.effective_user.id
    
    # 1. בדיקה אם הלקוח שלח טלפון בטקסט (תמיד עובד)
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    if phone_pattern.search(user_text):
        phone = phone_pattern.search(user_text).group(0)
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 ליד חדש (מתוך טקסט)!\n👤 {update.effective_user.first_name}\n📱 {phone}\n📝 תוכן: {user_text}")
        except: pass
        await context.bot.send_message(chat_id=update.effective_chat.id, text="תודה! רשמתי את הפרטים. סוכן יצור איתך קשר בהקדם. 🏠", reply_markup=get_main_keyboard())
        return

    # ניהול היסטוריה
    if user_id not in chats_history: chats_history[user_id] = []
    
    # 2. חיתוך לשיחה אנושית (רק אחרי 3 סבבים של שאלות ותשובות)
    # כל סבב = 2 הודעות (לקוח + בוט), אז 3 סבבים = 6 הודעות.
    if len(chats_history[user_id]) >= (MAX_MESSAGES * 2):
        cut_msg = (
            "תודה רבה על כל הפרטים! 😊\n"
            "יש לי מספיק מידע כדי להתאים לך נכסים מצוינים.\n\n"
            "כדי שסוכן אנושי יוכל לחזור אליך עם ההצעות, אנא לחץ על הכפתור למטה 👇"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=cut_msg, reply_markup=get_main_keyboard())
        return 

    # הכנת השיחה ל-AI
    history = ""
    for msg in chats_history[user_id][-6:]: history += f"{msg['role']}: {msg['text']}\n"

    if update.effective_chat.type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # שליחה לגוגל
    bot_answer = send_to_google(history, user_text)
    
    chats_history[user_id].append({"role": "user", "text": user_text})
    chats_history[user_id].append({"role": "model", "text": bot_answer})
    
    # תשובה למשתמש
    if update.effective_chat.type == 'private':
        await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer, reply_markup=get_main_keyboard())
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer, reply_to_message_id=update.message.message_id)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.message.contact
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 ליד חדש (כפתור)!\n👤 {c.first_name}\n📱 {c.phone_number}")
    except: pass
    await context.bot.send_message(chat_id=update.effective_chat.id, text="המספר התקבל בהצלחה! העברתי את התיק לסוכן המטפל. 🏠", reply_markup=get_main_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats_history[update.effective_user.id] = [] # איפוס היסטוריה בהתחלה
    # הנוסח המדויק שביקשת
    welcome_msg = "שלום, אני הבוט של הסוכנות Lina Real Estate בנתניה, במה אוכל לעזור לך היום?"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_msg, reply_markup=get_main_keyboard())

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("✅ הבוט רץ - גרסה חכמה (מכירה והשכרה)")
    app.run_polling()
