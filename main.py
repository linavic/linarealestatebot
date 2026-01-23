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
# 🧠 המוח: הנחיות ל-AI (וגם גיבוי ידני)
# ==========================================
SYSTEM_PROMPT = """
You are the receptionist for 'Lina Real Estate'.
Your goal is to qualify the lead.

Current conversation stage:
{STAGE_INSTRUCTION}

RULES:
- Answer in Hebrew.
- Be polite and professional.
- Keep it short.
- NEVER ask for a phone number yet.
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
                print(f"✅ מודל נבחר: {url}")
                return
        except: continue
    current_model_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"

find_working_model()

# ==========================================
# 🧠 שליחה ל-AI עם ניהול שלבים חכם
# ==========================================
def send_to_google(history_text, user_text, stage):
    # הגדרת ההוראה לפי השלב בשיחה
    stage_instruction = ""
    fallback_response = ""

    if stage == 1:
        stage_instruction = "The user just said what they want (Buy/Rent). Now ASK: 'How many rooms and what is the budget?'"
        fallback_response = "רשמתי לפני. כמה חדרים אתם מחפשים ומה התקציב בערך?"
    elif stage == 2:
        stage_instruction = "The user answered budget/rooms. Now ASK: 'Do you have a preferred area in Netanya?'"
        fallback_response = "מעולה. האם יש שכונה או אזור מסוים בנתניה שאתם מעדיפים?"
    else:
        stage_instruction = "Just say thank you and that you are checking."
        fallback_response = "תודה על כל הפרטים."

    headers = {'Content-Type': 'application/json'}
    # מכניסים את ההוראה הספציפית לתוך הפרומפט
    final_prompt = SYSTEM_PROMPT.replace("{STAGE_INSTRUCTION}", stage_instruction)
    
    payload = {
        "contents": [{
            "parts": [{"text": f"{final_prompt}\n\nהיסטוריה:\n{history_text}\nלקוח: {user_text}\nאני (המזכירה):"}]
        }]
    }
    try:
        response = requests.post(current_model_url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        return fallback_response # אם גוגל נכשל - מחזירים את השאלה הנכונה לשלב הזה!
    except:
        return fallback_response

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
    
    # 1. זיהוי טלפון בטקסט
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    if phone_pattern.search(user_text):
        phone = phone_pattern.search(user_text).group(0)
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 ליד בטקסט!\n{phone}\n{user_text}")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="תודה! המספר נשמר. סוכן יחזור אליך. 🏠", reply_markup=get_main_keyboard())
        return

    # ניהול היסטוריה
    if user_id not in chats_history: chats_history[user_id] = []
    
    # חישוב השלב בשיחה (0, 1, 2, 3...)
    # כל הודעה של המשתמש מקדמת אותנו שלב
    # len=0 -> התחלה
    # len=2 -> המשתמש ענה על שאלה ראשונה (שלב 1)
    # len=4 -> המשתמש ענה על שאלה שניה (שלב 2)
    conversation_stage = (len(chats_history[user_id]) // 2) + 1

    # חיתוך לשיחה אנושית (אחרי שהמשתמש ענה על האזור - שלב 3)
    if conversation_stage >= 3:
        cut_msg = (
            "תודה רבה! יש לי את כל המידע כדי להתאים לך נכס בול. 🏠\n"
            "כדי שסוכן אנושי יחזור אליך עם ההצעות, חובה להשאיר מספר נייד.\n"
            "👇 **אנא לחץ על הכפתור למטה עכשיו** 👇"
        )
        await context.bot.send_message(chat_id=update.effective_chat.id, text=cut_msg, reply_markup=get_main_keyboard())
        return 

    # הכנת ההיסטוריה
    history = ""
    for msg in chats_history[user_id][-6:]: history += f"{msg['role']}: {msg['text']}\n"

    if update.effective_chat.type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # שליחה לגוגל עם השלב המדויק
    bot_answer = send_to_google(history, user_text, conversation_stage)
    
    chats_history[user_id].append({"role": "user", "text": user_text})
    chats_history[user_id].append({"role": "model", "text": bot_answer})
    
    if update.effective_chat.type == 'private':
        await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer, reply_markup=get_main_keyboard())
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=bot_answer, reply_to_message_id=update.message.message_id)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.message.contact
    await context.bot.send_message(chat_id=ADMIN_ID, text=f"🔔 ליד כפתור!\n{c.phone_number}\n{c.first_name}")
    await context.bot.send_message(chat_id=update.effective_chat.id, text="קיבלתי את המספר! סוכן שלנו יחייג אליך בקרוב. 🏠", reply_markup=get_main_keyboard())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats_history[update.effective_user.id] = []
    welcome_msg = "שלום, אני הבוט של הסוכנות Lina Real Estate בנתניה. במה אוכל לעזור לך היום? (קנייה או השכרה?)"
    await context.bot.send_message(chat_id=update.effective_chat.id, text=welcome_msg, reply_markup=get_main_keyboard())

if __name__ == '__main__':
    keep_alive()
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("✅ הבוט רץ - לוגיקה כפויה (מונע חזרות)")
    app.run_polling(drop_pending_updates=True)
