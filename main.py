import os
import logging
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
CORS(app)

# ניקוי מפתחות
def get_key(name):
    val = os.environ.get(name)
    return val.strip() if val else None

API_KEY = get_key("GEMINI_API_KEY")
TELEGRAM_TOKEN = get_key("TELEGRAM_TOKEN")
ADMIN_ID = get_key("ADMIN_ID")

chat_history = {}
CURRENT_MODEL_NAME = None # כאן נשמור את השם שהבוט ימצא לבד

# === פונקציית הקסם: מציאת מודל אוטומטית ===
def find_working_model():
    global CURRENT_MODEL_NAME
    if CURRENT_MODEL_NAME: return CURRENT_MODEL_NAME
    
    print("🔍 Scanning for available Google models...")
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            # מחפשים מודל שיודע לייצר טקסט
            for model in data.get('models', []):
                if 'generateContent' in model.get('supportedGenerationMethods', []):
                    # מצאנו! שומרים את השם המדויק (למשל models/gemini-1.5-flash-001)
                    CURRENT_MODEL_NAME = model['name']
                    print(f"✅ Auto-detected model: {CURRENT_MODEL_NAME}")
                    return CURRENT_MODEL_NAME
    except Exception as e:
        print(f"⚠️ Auto-detect failed: {e}")
    
    # ברירת מחדל אם הסריקה נכשלה
    print("⚠️ Using fallback model")
    return "models/gemini-1.5-flash"

# === התראות לטלגרם ===
def notify_lina(text):
    if not TELEGRAM_TOKEN or not ADMIN_ID: return
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                      json={"chat_id": ADMIN_ID, "text": text}, timeout=3)
    except: pass

# === השרת ===
@app.route('/')
def home():
    return "Lina Auto-Bot Active 🚀"

@app.route('/web-chat', methods=['POST'])
def web_chat():
    try:
        if not API_KEY: return jsonify({'reply': "שגיאה: חסר מפתח API."})

        data = request.json
        msg = data.get('message')
        uid = data.get('user_id', 'guest')

        # התראות רקע
        threading.Thread(target=notify_lina, args=(f"👤 *לקוח:* {msg}",)).start()
        if uid not in chat_history:
             threading.Thread(target=notify_lina, args=(f"🚀 לקוח חדש!",)).start()
        if any(char.isdigit() for char in msg) and len(msg) > 6:
            threading.Thread(target=notify_lina, args=(f"🔥 **ליד חם!**\n{msg}",)).start()

        # 1. מציאת המודל הנכון (רק בפעם הראשונה)
        model_name = find_working_model()
        
        # 2. ניהול שיחה
        history = chat_history.get(uid, [])
        history.append({"role": "user", "parts": [{"text": msg}]})
        
        payload = {
            "contents": history,
            "systemInstruction": {
                "parts": [{"text": "אתה העוזר של לינה (LINA Real Estate). ענה בעברית קצרה ומכירתית."}]
            }
        }

        # 3. שליחה לכתובת הדינמית
        # שים לב: model_name כבר כולל את המילה models/ אז לא מוסיפים אותה שוב
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={API_KEY}"
        
        response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'}, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and result['candidates']:
                bot_text = result['candidates'][0]['content']['parts'][0]['text']
                history.append({"role": "model", "parts": [{"text": bot_text}]})
                chat_history[uid] = history[-10:] 
                return jsonify({'reply': bot_text})
            else:
                return jsonify({'reply': "לא הבנתי, נסה שוב."})
        else:
            # אם גם זה נכשל - זה אומר שהמפתח עצמו חסום או לא תקין
            error_json = response.json()
            error_msg = error_json.get('error', {}).get('message', 'Unknown Error')
            return jsonify({'reply': f"תקלה במפתח: {error_msg}"})

    except Exception as e:
        return jsonify({'reply': "תקלה טכנית."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
