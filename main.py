import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

# === הגדרות בסיסיות ===
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
CORS(app)  # מאפשר לאתר לגשת לשרת

# === הגדרת המוח (Gemini) ===
GENAI_API_KEY = os.environ.get("GEMINI_API_KEY")

model = None
if GENAI_API_KEY:
    try:
        genai.configure(api_key=GENAI_API_KEY)
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction="""
            אתה העוזר האישי הדיגיטלי של לינה סוחוביצקי (LINA Real Estate).
            המטרה שלך: לתת שירות מעולה באתר האינטרנט.
            הנחיות:
            1. ענה בעברית, בצורה קצרה, שיווקית ומזמינה.
            2. המטרה הסופית היא לגרום ללקוח להתקשר: 054-4326270.
            3. אל תמציא נכסים שלא קיימים.
            """
        )
        print("✅ Gemini AI Connected Successfully")
    except Exception as e:
        print(f"❌ Error connecting to Gemini: {e}")
else:
    print("⚠️ Warning: GEMINI_API_KEY is missing in Render settings")

# זיכרון שיחות (נמחק כשהשרת עושה ריסטרט, וזה בסדר גמור לבוט באתר)
chat_sessions = {}

@app.route('/')
def home():
    return "Lina Website Bot is Active and Healthy! 🚀"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    # בדיקת תקינות בסיסית
    if not model:
        return jsonify({'reply': "הבוט בהפסקה קצרה (שגיאת חיבור למוח). נסה שוב מאוחר יותר."})

    try:
        data = request.json
        user_msg = data.get('message')
        user_id = data.get('user_id', 'guest')

        print(f"📩 הודעה חדשה משתמש {user_id}: {user_msg}")

        # יצירת שיחה חדשה אם צריך
        if user_id not in chat_sessions:
            chat_sessions[user_id] = model.start_chat(history=[])
        
        # שליחה ל-Gemini
        chat = chat_sessions[user_id]
        response = chat.send_message(user_msg)
        
        return jsonify({'reply': response.text})

    except Exception as e:
        print(f"❌ שגיאה בשיחה: {e}")
        # במקרה של שגיאה, מחזירים הודעה נעימה ולא קורסים
        return jsonify({'reply': "סליחה, הייתה לי הפרעה קטנה. תוכל לחזור על זה? או להתקשר ללינה: 054-4326270"})

if __name__ == "__main__":
    # הרצת השרת בפורט הנכון ש-Render מבקש
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
