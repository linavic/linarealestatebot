from flask import Flask, request, jsonify
from threading import Thread
from flask_cors import CORS
import google.generativeai as genai
import os

# יצירת השרת
app = Flask('')
CORS(app)  # פותח את הגישה לאתר שלך

# הגדרת Gemini (לוקח את המפתח מהגדרות Render)
GENAI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GENAI_API_KEY:
    genai.configure(api_key=GENAI_API_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction="""
        אתה העוזר האישי של משרד התיווך LINA Real Estate (לינה סוחוביצקי).
        עליך לענות ללקוחות באתר, להיות נחמד, קצר ולעניין.
        המטרה: לגרום להם להתקשר ללינה או להשאיר פרטים.
        טלפון של לינה: 054-4326270.
        דבר בעברית טבעית.
        """
    )
else:
    model = None
    print("Warning: GEMINI_API_KEY not set!")

# זיכרון שיחות
chat_sessions = {}

@app.route('/')
def home():
    return "I am alive! Telegram + Web Bot are running."

@app.route('/web-chat', methods=['POST'])
def web_chat():
    # בדיקה אם המודל נטען
    if not model:
        return jsonify({'reply': "שגיאת שרת: מפתח Gemini חסר."})

    try:
        data = request.json
        user_message = data.get('message')
        user_id = data.get('user_id', 'guest')

        # יצירת היסטוריה אם לא קיימת
        if user_id not in chat_sessions:
            chat_sessions[user_id] = model.start_chat(history=[])
        
        chat = chat_sessions[user_id]
        response = chat.send_message(user_message)
        
        return jsonify({'reply': response.text})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'reply': "סליחה, יש תקלה רגעית. נסה שוב או התקשר ללינה."})

def run():
    # הרצת השרת בפורט 8080 (סטנדרטי בבוטים כאלה)
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
