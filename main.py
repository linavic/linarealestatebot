import os
import logging
import asyncio
import google.generativeai as genai
from telegram import Update
from telegram.constants import ChatAction, ChatType
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters
)
from keep_alive import keep_alive

# ==========================================
# ⚙️ הגדרות
# ==========================================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# לוגים
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# 🧠 הגדרת גוגל + בחירת מודל אוטומטית
# ==========================================
if not GEMINI_API_KEY:
    print("❌ שגיאה: חסר מפתח GEMINI_API_KEY")
    model = None
else:
    genai.configure(api_key=GEMINI_API_KEY)
    
    print("🔍 סורק מודלים זמינים בחשבון שלך...")
    target_model = "gemini-1.5-flash" # ברירת מחדל
    
    try:
        # מבקש מגוגל את הרשימה האמיתית של המודלים הפתוחים למפתח הזה
        available_models = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                available_models.append(m.name)
        
        print(f"📋 המודלים שלך: {available_models}")

        # אלגוריתם חכם לבחירת המודל הכי טוב שקיים אצלך
        # עדיפות 1: Flash (מהיר)
        # עדיפות 2: Pro (חזק)
        # עדיפות 3: מה שיש
        
        found = False
        # מחפש גרסאות של פלאש
        for m in available_models:
            if "flash" in m and "1.5" in m:
                target_model = m
                found = True
                break
        
        if not found:
            # אם אין פלאש, מחפש פרו
            for m in available_models:
                if "pro" in m and "1.5" in m:
                    target_model = m
                    found = True
                    break
        
        if not found and available_models:
             # אם לא מצאנו את המועדפים, לוקחים את הראשון ברשימה וזהו
             target_model = available_models[0]

    except Exception as e:
        print(f"⚠️ שגיאה בסריקה (נשתמש בברירת מחדל): {e}")

    # מנקה את השם (לפעמים מגיע עם models/ בהתחלה)
    if target_model.startswith("models/"):
        target_model = target_model.replace("models/", "")
        
    print(f"✅ נבחר המודל: {target_model}")
    model = genai.GenerativeModel(target_model)

SYSTEM_PROMPT = (
    "את Lina, סוכנת נדל\"ן מקצועית בנתניה. "
    "עני בעברית, בצורה קצרה (עד 2 משפטים) ומזמינה. "
    "המטרה: לעזור ללקוח או לקבל טלפון."
)

# ==========================================
# 🧠 פונקציה לשליחה לגוגל
# ==========================================
def ask_gemini(text: str) -> str:
    if not model:
        return "תקלת הגדרות במפתח גוגל."

    try:
        prompt = f"{SYSTEM_PROMPT}\nUser: {text}\nLina:"
        # timeout מונע תקיעות
        response = model.generate_content(prompt, request_options={'timeout': 10})
        return response.text.strip()
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        # במקרה של שגיאה, מחזיר הודעה ברורה
        return f"שגיאה טכנית: {str(e)[:50]}..." 

# ==========================================
# 📩 טיפול בהודעות
# ==========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    
    # מניעת לופים מערוצים
    if update.effective_user.id == 777000: return

    text = update.message.text
    chat_type = update.effective_chat.type
    bot_username = context.bot.username

    # --- סינון קבוצות חכם ---
    if chat_type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        # עונים רק אם תייגו אותנו או הגיבו לנו
        is_mentioned = f"@{bot_username}" in text
        is_reply = (update.message.reply_to_message and 
                    update.message.reply_to_message.from_user.id == context.bot.id)
        
        if not (is_mentioned or is_reply):
            return 

        text = text.replace(f"@{bot_username}", "").strip()

    # חיווי הקלדה (רק בפרטי)
    if chat_type == 'private':
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    # שליחה לגוגל ברקע
    loop = asyncio.get_running_loop()
    try:
        answer = await loop.run_in_executor(None, ask_gemini, text)
        
        if chat_type == 'private':
            await update.message.reply_text(answer)
        else:
            await update.message.reply_text(answer, quote=True)
            
    except Exception as e:
        print(f"Telegram Error: {e}")

# ==========================================
# 🚀 התחלה
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("היי! אני לינה 🏠\nאיך אני יכולה לעזור?")

if __name__ == "__main__":
    keep_alive()

    if not TELEGRAM_BOT_TOKEN:
        print("❌ חסר טוקן")
    else:
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        print("🤖 הבוט רץ! (מצב זיהוי מודל אוטומטי)")
        app.run_polling()
