import os
import logging
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
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("❌ TELEGRAM_BOT_TOKEN חסר")
if not GEMINI_API_KEY:
    raise RuntimeError("❌ GEMINI_API_KEY חסר")

logging.basicConfig(level=logging.INFO)

# ==========================================
# 🧠 Gemini – מודל יציב
# ==========================================
genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel(
    model_name="gemini-pro"
)

SYSTEM_PROMPT = (
    "את Lina, סוכנת נדל\"ן מקצועית בישראל. "
    "עני תמיד בעברית, בצורה ברורה, קצרה ומקצועית."
)

# ==========================================
# 🧠 פונקציית AI
# ==========================================
def ask_gemini(user_text: str) -> str:
    try:
        prompt = f"{SYSTEM_PROMPT}\n\nשאלה: {user_text}"

        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.4,
                "max_output_tokens": 500,
            }
        )

        if not response or not response.text:
            return "⚠️ לא התקבלה תשובה מהמודל."

        return response.text.strip()

    except Exception as e:
        logging.exception("Gemini Error")
        return f"⚠️ שגיאת Gemini:\n{e}"

# ==========================================
# 📩 טיפול בהודעות
# ==========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat_type = update.effective_chat.type
    message_text = update.message.text
    bot_username = context.bot.username

    # -------------------------------
    # 🛑 סינון קבוצות
    # -------------------------------
    if chat_type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        mentioned = f"@{bot_username}" in message_text
        replied_to_bot = (
            update.message.reply_to_message
            and update.message.reply_to_message.from_user
            and update.message.reply_to_message.from_user.username == bot_username
        )

        if not mentioned and not replied_to_bot:
            return  # ❌ מתעלם מהודעה בקבוצה

        # מנקה mention מהטקסט
        message_text = message_text.replace(f"@{bot_username}", "").strip()

    # -------------------------------
    # ✍️ חיווי הקלדה
    # -------------------------------
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING
    )

    # -------------------------------
    # 🤖 תשובת AI
    # -------------------------------
    answer = ask_gemini(message_text)
    await update.message.reply_text(answer)

# ==========================================
# 🚀 start
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 שלום! אני Lina, סוכנת נדל\"ן חכמה.\n"
        "בפרטי – עונה תמיד.\n"
        "בקבוצה – עונה רק כשמתייגים אותי 😊"
    )

# ==========================================
# ▶️ הרצה
# ==========================================
if __name__ == "__main__":
    keep_alive()

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot is running...")
    app.run_polling()
