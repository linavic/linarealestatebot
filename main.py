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

# מספר ההודעות שהבוט יתשאל לפני שיעביר לנציג אנושי
MAX_MESSAGES = 4 

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==========================================
# 🧠 המוח החדש (שואל, מתעניין, ורק בסוף מבקש טלפון)
# ==========================================
SYSTEM_PROMPT = """
You are the intelligent digital assistant for 'Lina Real Estate' in Netanya.
Language: Hebrew.
Tone: Warm, professional, curious, and helpful.
Your Goal: Qualify the lead by asking 2-3 relevant questions BEFORE asking for contact details.

Guidelines:
1. **DO NOT ask for a phone number in the first 2 messages.**
2. First, ask what they are looking for (Buy/Rent? Investment/Living?).
3. Then, ask about preferences (Budget? Area in Netanya? Number of rooms?).
4. Act like a helpful secretary preparing the file for the human agent.
5. Keep answers short (1-3 sentences).
6. Be polite and show interest in their answers ("Sounds great!", "I see.").
"""

chats_history = {}
current_model_url = ""

# ==========================================
# 🔍 סורק מודלים (למניעת 404)
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
            "parts": [{"text": f"{SYSTEM_PROMPT}\n\nהיסטוריה קודמת:\n{history_text}\nלקוח: {user_text}\nאני (העוזר הדיגיטלי):"}]
        }]
    }
    try:
        response = requests.post(current_model_url, json=payload, headers=headers, timeout=15)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        return "אני רושם את הפרטים. כדי שנתקדם, אשמח למספר נייד."
    except:
        return "יש לי הפרעה קטנה, אשמח אם תשאיר מספר נייד."

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
    
    # 1. תפיסת מספר טלפון (תמיד בעדיפות עליונה)
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    if phone_pattern.search(user_text):
        phone = phone_pattern.search(user_text).group(0)
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 ליד חדש (מתוך טקסט)!\n👤 {update.effective_user.first_name}\n📱 {phone}\n📝 תוכן: {user_text}")
        except: pass
        await context.bot.send_message(chat_id=update.effective_chat.id, text="תודה רבה! רשמתי את כל הפרטים. לינה או אחד הסוכנים יחזרו אליך בהקדם לשיחה אישית. 🏠", reply_markup=get_main_keyboard())
        return

    # ניהול היסטוריה
    if user_id not in chats_history: chats_history[user_id] = []
    
    # 2. חיתוך לשיחה אנושית (אחרי 4 הודעות)
    if len(chats_history[user_id]) >= (MAX_MESSAGES * 2):
        cut_msg = (
            "תודה על כל המידע! 😊\n"
            "כדי לתת לך את השירות המדויק ביותר, אני מעביר את הפרטים שלך לטיפול אישי של סוכן אנושי.\n\n"
            "אנא לחץ על הכפתור למטה (או כתוב את המספר שלך) כדי שלינה תוכל לחזור אליך עם הצעות רלוונטיות. 👇"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=cut_msg, reply_markup=get_main_keyboard())
        return 

    # הכנת ההיסטוריה
    history = ""
    for msg in chats_history[user_id][-6:]: history += f"{msg['role']}: {msg['text']}\n"

    if update.effective_chat.type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # שליחה לגוגל
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
    await context.bot.send_message(chat_id=update.effective_chat.id, text="המספר התקבל בהצלחה! העברתי את הפרטים ללינה להמשך טיפול. 🏠", reply_markup=get_main_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats_history[update.effective_user.id] = [] # איפוס
    welcome_msg = (
        "היי! אני העוזר הדיגיטלי של לינה נדל\"ן 🏠\n"
        "אני כאן כדי לעזור לך למצוא את הנכס המושלם או למכור את הנכס שלך.\n\n"
        "כדי שנתחיל, האם את/ה מתעניין/ת בקנייה, מכירה או השכרה?"
    )
    await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_msg, reply_markup=get_main_keyboard())

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("✅ הבוט רץ (מצב: עוזר חכם ושואל שאלות)")
    app.run_polling()
