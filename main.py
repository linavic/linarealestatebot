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
# 🧠 חיבור לגוגל Gemini - גרסת חירום עם ניסיונות מרובים
# ==========================================
def send_to_google_gemini(history_text, user_text):
    """ מנסה מספר גרסאות של Gemini API """
    
    # רשימת כל המודלים האפשריים עם גרסאות API שונות
    endpoints_to_try = [
        # גרסה 1.5 - העדכנית ביותר
        {
            "name": "gemini-1.5-flash-latest",
            "url": f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_API_KEY}"
        },
        {
            "name": "gemini-1.5-flash",
            "url": f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        },
        {
            "name": "gemini-1.5-pro-latest",
            "url": f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro-latest:generateContent?key={GEMINI_API_KEY}"
        },
        # גרסה 1.0 - לגיבוי
        {
            "name": "gemini-1.0-pro-latest",
            "url": f"https://generativelanguage.googleapis.com/v1/models/gemini-1.0-pro-latest:generateContent?key={GEMINI_API_KEY}"
        },
        # גרסאות v1beta לגיבוי
        {
            "name": "gemini-1.5-flash (v1beta)",
            "url": f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        },
        {
            "name": "gemini-1.0-pro (v1beta)",
            "url": f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.0-pro:generateContent?key={GEMINI_API_KEY}"
        }
    ]
    
    headers = {'Content-Type': 'application/json'}
    
    # בניית ההודעות למערכת
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
    
    # הוספת ההיסטוריה אם יש
    if history_text and history_text.strip():
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
        }
    }
    
    last_error = ""
    
    # ניסיון כל המודלים ברשימה
    for endpoint in endpoints_to_try:
        try:
            print(f"🔄 מנסה מודל: {endpoint['name']}")
            response = requests.post(endpoint['url'], json=payload, headers=headers, timeout=15)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    print(f"✅ הצלחה עם מודל: {endpoint['name']}")
                    return result['candidates'][0]['content']['parts'][0]['text']
                else:
                    last_error = f"התשובה ריקה ממודל {endpoint['name']}"
                    continue
            else:
                last_error = f"Error {response.status_code} במודל {endpoint['name']}: {response.text[:100]}"
                print(f"⚠️ {last_error}")
                continue
                
        except Exception as e:
            last_error = f"שגיאת חיבור במודל {endpoint['name']}: {str(e)}"
            continue
    
    # אם כל הניסיונות נכשלו
    error_message = f"""לא הצלחתי להתחבר למערכת ה-AI.

{last_error}

📱 לשירות מהיר, פנה ישירות לווטסאפ:
https://wa.me/972544326270

או ליצור קשר דרך:
📞 054-4326270
📧 office@linarealestate.net

אשמח לעזור לך עם כל שאלה בנדל"ן! 🏠"""
    
    return error_message

# ==========================================
# 📩 הנדלרים
# ==========================================

async def send_lead_alert(context, name, username, phone, source):
    msg = f"🔔 <b>ליד חדש!</b>\n👤 {name}\n📱 {phone}\n📝 {source}"
    try:
        await context.bot.send_message(chat_id=ADMIN_ID, text=msg, parse_mode='HTML')
        print(f"✅ נשלחה התראה על ליד: {phone}")
    except Exception as e:
        print(f"❌ שגיאה בשליחת התראה: {str(e)}")

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    c = update.message.contact
    user_name = update.effective_user.first_name or "ללא שם"
    
    await send_lead_alert(context, user_name, update.effective_user.username, c.phone_number, "כפתור שיתוף")
    
    response_text = f"""תודה {user_name}! המספר שלך נקלט במערכת.

אחזור אליך בהקדם האפשרי.

לשירות מהיר יותר, תוכל לפנות גם ישירות לווטסאפ:
https://wa.me/972544326270

או להתקשר ל:
📞 054-4326270"""
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=response_text,
        reply_markup=get_main_keyboard(),
        disable_web_page_preview=True
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: 
        return
    
    # התעלמות מהודעות מערוצים
    if update.effective_user.id == 777000: 
        return
    
    user_text = update.message.text
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "המשתמש"
    
    # זיהוי טלפון בהודעה
    phone_pattern = re.compile(r'05\d{1}[- ]?\d{3}[- ]?\d{4}')
    phone_match = phone_pattern.search(user_text)
    
    if phone_match:
        phone = phone_match.group(0)
        await send_lead_alert(context, user_name, update.effective_user.username, phone, f"טקסט: {user_text[:50]}")
        
        response_text = f"""רשמתי את המספר, תודה {user_name}! 

אחזור אליך בהקדם האפשרי.

לשירות מהיר יותר, תוכל לפנות גם ישירות לווטסאפ:
https://wa.me/972544326270

או להתקשר ל:
📞 054-4326270"""
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=response_text,
            reply_markup=get_main_keyboard(),
            disable_web_page_preview=True
        )
        return
    
    # ניהול היסטוריה
    if user_id not in chats_history: 
        chats_history[user_id] = []
    
    # הגבלת גודל ההיסטוריה
    history_list = chats_history[user_id]
    if len(history_list) > 10:  # 5 הודעות משתמש + 5 הודעות בוט
        history_list = history_list[-10:]
        chats_history[user_id] = history_list
    
    # בניית טקסט היסטוריה
    history_text = ""
    for msg in history_list[-6:]:  # רק 3 הודעות אחרונות מכל צד
        role_name = "משתמש" if msg['role'] == "user" else "לינה"
        history_text += f"{role_name}: {msg['text']}\n"
    
    # שליחת פעולת הקלדה
    if update.effective_chat.type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    # קבלת תשובה מ-Gemini
    print(f"📥 הודעה מ-{user_name}: {user_text[:50]}...")
    bot_answer = send_to_google_gemini(history_text, user_text)
    print(f"📤 תשובה ל-{user_name}: {bot_answer[:50]}...")
    
    # עדכון היסטוריה
    chats_history[user_id].append({"role": "user", "text": user_text})
    chats_history[user_id].append({"role": "model", "text": bot_answer})
    
    # שליחת התשובה
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=bot_answer, 
        reply_markup=get_main_keyboard(),
        disable_web_page_preview=True
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or ""
    
    # איפוס היסטוריה
    chats_history[user_id] = []
    
    welcome_msg = f"""היי{f' {user_name}' if user_name else ''}! אני לינה נדל"ן 🏠

אני כאן לעזור לך בכל שאלה בנושא נדל"ן בנתניה והסביבה:
• קנייה ומכירה של דירות
• השכרת נכסים
• יעוץ משכנתאות
• שיפוצים ושיפוץ נכסים

📞 **ליצירת קשר ישיר:**
• ווטסאפ: https://wa.me/972544326270
• טלפון: 054-4326270
• מייל: office@linarealestate.net

לחצו על הכפתור למטה כדי לשתף את מספר הטלפון שלכם, או פשוט כתבו לי שאלה!"""
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=welcome_msg, 
        reply_markup=get_main_keyboard(),
        disable_web_page_preview=True,
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """🆘 **עזרה - Lina נדל"ן**

**פקודות זמינות:**
/start - התחל שיחה חדשה
/help - הצג הודעה זו

**דרכי יצירת קשר ישירות:**
📱 ווטסאפ: https://wa.me/972544326270
📞 טלפון: 054-4326270
📧 מייל: office@linarealestate.net

**מה אני יכולה לעזור לך?**
• מידע על נכסים למכירה/השכרה
• יעוץ משכנתאות
• הערכת שווי נכס
• ליווי עסקאות

פשוט שלחו לי הודעה או לחצו על הכפתור למטה!"""
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=help_text,
        reply_markup=get_main_keyboard(),
        disable_web_page_preview=True,
        parse_mode='Markdown'
    )

# ==========================================
# 🚀 הפעלת הבוט
# ==========================================
if __name__ == '__main__':
    keep_alive()
    
    print("=" * 50)
    print("🚀 מתחיל את LinaRealEstateBot")
    print("=" * 50)
    
    # בדיקת מפתחות
    if not TELEGRAM_BOT_TOKEN:
        print("❌ שגיאה: חסר TELEGRAM_BOT_TOKEN")
        print("⚠️ אנא הגדר את המשתנה בסביבה")
        exit(1)
    
    if not GEMINI_API_KEY:
        print("❌ שגיאה: חסר GEMINI_API_KEY")
        print("⚠️ אנא הגדר את המשתנה בסביבה")
        exit(1)
    
    print("✅ כל המפתחות זמינים")
    print(f"🔑 TELEGRAM_BOT_TOKEN: {'****' + TELEGRAM_BOT_TOKEN[-4:] if TELEGRAM_BOT_TOKEN else 'לא קיים'}")
    print(f"🔑 GEMINI_API_KEY: {'****' + GEMINI_API_KEY[-4:] if GEMINI_API_KEY else 'לא קיים'}")
    
    # בניית האפליקציה
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # הוספת handlers
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("\n✅ הבוט מוכן לפעולה!")
    print("📱 שם: LinaRealEstateBot")
    print("🧠 מנגנון: Gemini AI עם ניסיונות מרובים")
    print("⏳ מחכה להודעות...")
    
    try:
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
    except Exception as e:
        print(f"\n❌ שגיאה קריטית: {str(e)}")
        print("🔄 נסה להפעיל מחדש...")
