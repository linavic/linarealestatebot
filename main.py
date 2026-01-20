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

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    print("❌ שגיאה: חסרים מפתחות ב-Secrets!")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

SYSTEM_PROMPT = """את Lina, סוכנת נדל"ן בנתניה. את מומחית בנדל"ן, אדיבה ומועילה.
תמיד עני בעברית, קצר ומקצועי.
אל תמציא מידע על נכסים שאין לך.
אם מישהו שולח לך מספר טלפון, תגידי "רשמתי את המספר, תודה!" ותזכירי שאת זמינה בווטסאפ."""

chats_history = {}

# ==========================================
# 🧠 המקלדת
# ==========================================
def get_main_keyboard():
    button = KeyboardButton("📞 שלח את המספר שלי ללינה", request_contact=True)
    return ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=False)

# ==========================================
# 🧠 חיבור לגוגל Gemini
# ==========================================
def send_to_google_gemini(history_text, user_text):
    """ שולח הודעה ל-Google Gemini API """
    
    # גרסת API עדכנית (גרסה 1 יציבה)
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
    
    headers = {'Content-Type': 'application/json'}
    
    # מערכת ההיסטוריה
    contents = []
    
    # הוספת הנחיית המערכת
    contents.append({
        "role": "user",
        "parts": [{"text": SYSTEM_PROMPT}]
    })
    contents.append({
        "role": "model",
        "parts": [{"text": "בסדר, אני מוכנה לעזור כסוכנת הנדל\"ן לינה."}]
    })
    
    # הוספת ההיסטוריה
    if history_text:
        contents.append({
            "role": "user",
            "parts": [{"text": f"הנה היסטוריית השיחה:\n{history_text}"}]
        })
    
    # הוספת ההודעה הנוכחית
    contents.append({
        "role": "user",
        "parts": [{"text": user_text}]
    })
    
    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.7,
            "topP": 0.8,
            "topK": 40,
            "maxOutputTokens": 500,
        },
        "safetySettings": [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                return result['candidates'][0]['content']['parts'][0]['text']
            else:
                return "לא הצלחתי לקבל תשובה מהמערכת. נסה שוב או פנה ישירות לווטסאפ."
        else:
            error_msg = f"שגיאה {response.status_code}: "
            if response.status_code == 404:
                error_msg += "המודל לא נמצא. בדוק את שם המודל."
            elif response.status_code == 400:
                error_msg += "בקשה לא תקינה. ייתכן שהקלט ארוך מדי."
            elif response.status_code == 403:
                error_msg += "אין הרשאות. בדוק את ה-API Key."
            elif response.status_code == 429:
                error_msg += "יותר מדי בקשות. המתן מעט."
            else:
                error_msg += response.text[:200]
            
            logging.error(f"שגיאת Gemini: {error_msg}")
            
            # הודעה ידידותית למשתמש
            return f"""לא הצלחתי להגיב כרגע דרך המערכת. 

לשירות מהיר יותר, אתה מוזמן לפנות ישירות:
📱 ווטסאפ: https://wa.me/972544326270
📞 טלפון: 054-4326270
📧 מייל: office@linarealestate.net

אשמח לעזור לך עם כל שאלה בנדל"ן! 🏠"""
                
    except Exception as e:
        logging.error(f"שגיאה בחיבור ל-Gemini: {str(e)}")
        return "יש בעיה בחיבור למערכת. נסה שוב מאוחר יותר או פנה ישירות לווטסאפ."

# ==========================================
# 📩 הנדלרים
# ==========================================

async def send_lead_alert(context, name, username, phone, source):
    msg = f"🔔 <b>ליד חדש!</b>\n👤 {name}\n📱 {phone}\n📝 {source}"
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode='HTML')
    except Exception as e:
        logging.error(f"שגיאה בשליחת התראה: {str(e)}")

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.message.contact
    await send_lead_alert(context, update.effective_user.first_name, update.effective_user.username, c.phone_number, "כפתור שיתוף")
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text="תודה! המספר נקלט. אחזור אליך בהקדם.\n\nלשירות מהיר יותר, תוכל לפנות גם לווטסאפ:\nhttps://wa.me/972544326270",
        reply_markup=get_main_keyboard()
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: 
        return
    
    # התעלמות מהודעות מערוצים
    if update.effective_user.id == 777000: 
        return
    
    user_text = update.message.text
    user_id = update.effective_user.id
    
    # זיהוי טלפון בהודעה
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    phone_match = phone_pattern.search(user_text)
    
    if phone_match:
        phone = phone_match.group(0)
        await send_lead_alert(context, update.effective_user.first_name, update.effective_user.username, phone, f"טקסט: {user_text}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="רשמתי את המספר, תודה! אחזור אליך בהקדם.\n\nלשירות מהיר יותר, תוכל לפנות גם לווטסאפ:\nhttps://wa.me/972544326270",
            reply_markup=get_main_keyboard()
        )
        return  # לא ממשיכים לעיבוד נוסף אחרי זיהוי טלפון
    
    # ניהול היסטוריה
    if user_id not in chats_history: 
        chats_history[user_id] = []
    
    # שמירת היסטוריה מוגבלת (4 הודעות אחרונות מכל צד)
    history_list = chats_history[user_id]
    if len(history_list) > 8:  # 4 הודעות משתמש + 4 הודעות בוט
        history_list = history_list[-8:]
    
    history_text = ""
    for msg in history_list:
        role_name = "משתמש" if msg['role'] == "user" else "לינה"
        history_text += f"{role_name}: {msg['text']}\n"
    
    # שליחת פעולת הקלדה
    if update.effective_chat.type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # קבלת תשובה מ-Gemini
    bot_answer = send_to_google_gemini(history_text, user_text)
    
    # עדכון היסטוריה
    chats_history[user_id].append({"role": "user", "text": user_text})
    chats_history[user_id].append({"role": "model", "text": bot_answer})
    
    # שליחת התשובה
    if update.effective_chat.type == 'private':
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=bot_answer, 
            reply_markup=get_main_keyboard(),
            disable_web_page_preview=True
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=bot_answer, 
            reply_to_message_id=update.message.message_id,
            disable_web_page_preview=True
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chats_history[update.effective_user.id] = []
    welcome_msg = """היי! אני לינה נדל"ן 🏠

אני כאן לעזור לך בכל שאלה בנושא נדל"ן בנתניה והסביבה.

לשירות מהיר ואישי יותר, מומלץ לפנות ישירות לווטסאפ:
📱 https://wa.me/972544326270

או ליצור קשר דרך:
📞 טלפון: 054-4326270
📧 מייל: office@linarealestate.net

אשמח לעזור לך למכור, לקנות או להשכיר נכס!"""
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=welcome_msg, 
        reply_markup=get_main_keyboard(),
        disable_web_page_preview=True
    )

# ==========================================
# 🚀 הפעלת הבוט
# ==========================================
if __name__ == '__main__':
    keep_alive()
    
    # בדיקה שהמפתחות קיימים
    if not TELEGRAM_BOT_TOKEN:
        print("❌ שגיאה: חסר TELEGRAM_BOT_TOKEN")
        exit(1)
    if not GEMINI_API_KEY:
        print("❌ שגיאה: חסר GEMINI_API_KEY")
        exit(1)
    
    # בניית האפליקציה
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # הוספת handlers
    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("✅ הבוט רץ עם גרסת Gemini מעודכנת!")
    print("📱 שם הבוט: LinaRealEstateBot")
    print("🧠 משתמש במודל: gemini-1.5-flash-latest")
    
    try:
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        print(f"❌ שגיאה קריטית: {str(e)}")
