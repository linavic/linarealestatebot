import os
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
CORS(app)

# ניקוי רווחים מהמפתח (קריטי!)
def get_key(name):
    val = os.environ.get(name)
    return val.strip() if val else None

API_KEY = get_key("GEMINI_API_KEY")

# שימוש במודל PRO בלבד (היציב ביותר)
GOOGLE_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={API_KEY}"

chat_history = {}

@app.route('/')
def home():
    return "Lina Bot (Lite Version) is Active 🟢"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    try:
        if not API_KEY:
            return jsonify({'reply': "שגיאה: חסר מפתח API בשרת."})

        data = request.json
        msg = data.get('message')
        uid = data.get('user_id', 'guest')

        # ניהול היסטוריה
        history = chat_history.get(uid, [])
        history.append({"role": "user", "parts": [{"text": msg}]})

        # בניית הבקשה לגוגל
        payload = {
            "contents": history,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 150
            }
        }

        # הוספת הנחיה רק בהודעה הראשונה
        if len(history) == 1:
            history[0]["parts"][0]["text"] = f"אתה העוזר של לינה (LINA Real Estate). ענה בעברית קצרה ומכירתית. המשתמש אמר: {msg}"

        # שליחה (timeout ארוך של 30 שניות למנוע ניתוקים)
        response = requests.post(GOOGLE_URL, json=payload, headers={'Content-Type': 'application/json'}, timeout=30)

        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and result['candidates']:
                bot_text = result['candidates'][0]['content']['parts'][0]['text']
                # שמירה והחזרה
                history.append({"role": "model", "parts": [{"text": bot_text}]})
                chat_history[uid] = history[-10:] 
                return jsonify({'reply': bot_text})
            else:
                return jsonify({'reply': "לא הבנתי, נסה לנסח שוב."})
        else:
            # במקרה של שגיאה - נציג אותה כדי שתדעי אם המפתח חסום
            error_json = response.json()
            error_msg = error_json.get('error', {}).get('message', 'Unknown Error')
            print(f"Google Error: {error_msg}")
            return jsonify({'reply': f"תקלה במפתח גוגל: {error_msg}"})

    except Exception as e:
        print(f"System Error: {e}")
        return jsonify({'reply': "תקלה בשרת (נסה שוב בעוד רגע)."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
