import pickle
from flask import Flask, render_template, request, redirect, session
import os
import sqlite3
from datetime import datetime
import pytesseract
from PIL import Image
import requests
from bs4 import BeautifulSoup
# from transformers import pipeline

# ================= BASIC =================
app = Flask(__name__)
app.secret_key = "secret123"

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

print("DB PATH:", os.path.abspath('database.db'))

# ================= DATABASE =================
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        mobile TEXT
    )
    ''')

    c.execute('''
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        news TEXT,
        result TEXT,
        user_id INTEGER,
        date TEXT
    )
    ''')

    conn.commit()
    conn.close()

init_db()

# ================= LOAD MODEL =================
model = pickle.load(open("models/svm_model.pkl", "rb"))
vectorizer = pickle.load(open("models/vectorizer.pkl", "rb"))

import re

def clean_text(text):
    text = text.lower()
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"[^a-zA-Z ]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def svm_predict(text):

    text = clean_text(text)

    vec = vectorizer.transform([text])
    pred = model.predict(vec)[0]

    # 🔥 REAL CONFIDENCE
    decision = model.decision_function(vec)[0]
    confidence = min(95, max(60, int(abs(decision) * 20)))

    if pred == 1:
        return "Real News", confidence, "Language patterns match verified news articles", ""
    else:
        return "Fake News", confidence, "Detected misleading or non-credible language patterns", ""
    
# # ==============================
# # 🔥 RULE-BASED CHECK
# # ==============================
# def rule_based_check(text):
#     text_lower = text.lower()

#     fake_keywords = [
#         "shocking", "secret", "exposed", "miracle",
#         "you won't believe", "hidden truth"
#     ]

#     for word in fake_keywords:
#         if word in text_lower:
#             return "Fake News", 80, "Contains sensational keywords", ""

#     return None


# # ==============================
# # 🔥 GOOGLE FACT CHECK
# # ==============================
# def google_fact_check(query):

    
#     API_KEY = os.getenv("GOOGLE_API_KEY")
#     # API_KEY = "YOUR_NEWS_API_KEY"
    
#     if not API_KEY:
#         return None

#     url = f"https://factchecktools.googleapis.com/v1alpha1/claims:search?query={query}&key={API_KEY}"

#     try:
#         response = requests.get(url).json()
#         claims = response.get("claims", [])

#         if not claims:
#             return None

#         rating = claims[0]["claimReview"][0]["textualRating"].lower()

#         if "false" in rating:
#             return "Fake News", 95, "Verified false", ""
#         elif "true" in rating:
#             return "Real News", 95, "Verified true", ""
#         else:
#             return "Suspicious", 80, rating, ""

#     except:
#         return None


# # ==============================
# # 🔥 NEWS API CHECK
# # ==============================
# def news_verification(query):

#     API_KEY = "YOUR_NEWS_API_KEY"

#     url = f"https://newsapi.org/v2/everything?q={query}&apiKey={API_KEY}"

#     try:
#         response = requests.get(url).json()
#         articles = response.get("articles", [])

#         if len(articles) >= 5:
#             return "Real News", 85, "Reported by multiple sources", ""
#         elif len(articles) >= 2:
#             return "Suspicious", 60, "Limited coverage", ""
#         else:
#             return None

#     except:
#         return None


# ==============================
# 🔥 FINAL PREDICT FUNCTION
# ==============================
def predict_news(text):

    text = clean_text(text)

    vec = vectorizer.transform([text])

    pred = model.predict(vec)[0]
    prob = model.predict_proba(vec)[0]

    confidence = int(max(prob) * 100)

    if pred == 1:
        return "Real News", confidence, "Based on statistical language patterns", ""
    else:
        return "Fake News", confidence, "Detected misleading language patterns", ""

def extract_from_url(url):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(url, headers=headers, timeout=5)

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")

        paragraphs = soup.find_all("p")
        text = " ".join([p.get_text() for p in paragraphs])

        return text.strip()

    except:
        return None

# ================= ROUTES =================

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/detect')
def detect():
    return render_template('detect.html')


# ================= PREDICT =================

@app.route('/predict', methods=['POST'])
def predict():
    
    
    text = request.form.get('news')
    url = request.form.get('url')
    image = request.files.get('image')

    final_text = ""

    # 🔒 CHECK LOGIN STATUS
    is_logged_in = session.get('user_id')

    # ✅ TEXT (allowed for everyone)
    if text and text.strip():
        final_text = text.strip()

    # 🚫 URL (ONLY LOGGED IN USERS)
    elif url and url.strip():

        if not session.get('user_id'):
           return render_template("detect.html",
              error="🔒 URL feature available for logged-in users only")

        final_text = extract_from_url(url)

        if not final_text or len(final_text.split()) < 20:
           return render_template(
              "detect.html",
               error="⚠️ Unable to extract readable article content"
        )

    


    # 🚫 IMAGE (ONLY LOGGED IN USERS)
    elif image and image.filename != "":
        if not is_logged_in:
            return render_template("detect.html", 
                                   error="🔒 Image upload available for logged-in users only")

        from PIL import Image
        try:
            img = Image.open(image)
            final_text = pytesseract.image_to_string(img, config='--psm 6')
        except:
            return render_template("detect.html", error="Image processing failed")

    final_text = final_text.replace("\n", " ").strip()

    if not final_text:
        return render_template("detect.html", error="No readable text found")


    
     # ----------------------------
    # 🔥 INPUT VALIDATION
    # ----------------------------
    if len(final_text.split()) < 5:
        return render_template("detect.html", error="⚠️ Enter meaningful news text")

    if len(final_text) > 2000:
        return render_template("detect.html", error="⚠️ Text too long (max 2000 chars)")

    if len(set(final_text.split())) < 3:
        return render_template("detect.html", error="⚠️ Invalid or repetitive text")

    label, confidence, reason, sub_label = predict_news(final_text)
    print("FINAL:", label, confidence)
    
    # ----------------------------
    # 🔥 GUEST LIMIT (3/day)
    # ----------------------------
    if not session.get('user_id'):

        today = datetime.now().strftime("%Y-%m-%d")

        if session.get('guest_date') != today:
            session['guest_date'] = today
            session['guest_count'] = 0

        if session.get('guest_count', 0) >= 3:
            return render_template(
                "detect.html",
                error="⚠️ Free limit reached (3/day). Please login."
            )

        session['guest_count'] = session.get('guest_count', 0) + 1

    # ----------------------------
    # 🔥 DAILY LIMIT (20 for users)
    # ----------------------------
    if session.get('user_id'):

        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        today = datetime.now().strftime("%Y-%m-%d")

        c.execute("""
            SELECT COUNT(*) FROM history
            WHERE user_id = ? AND date LIKE ?
        """, (session['user_id'], today + "%"))

        today_count = c.fetchone()[0]

        if today_count >= 50:
            conn.close()
            return render_template(
                "detect.html",
                error="⚠️ Daily limit reached (50 checks). Try tomorrow."
            )
        conn.close()


    # 🔥 SAVE HISTORY (ONLY IF USER LOGGED IN)
    if session.get('user_id'):
        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        c.execute(
            "INSERT INTO history (news, result, user_id, date) VALUES (?, ?, ?, ?)",
            (
                final_text,
                label,
                session['user_id'],
                datetime.now().strftime("%Y-%m-%d %H:%M")
            )
        )

        conn.commit()
        conn.close()
    if label == "Real News":
       prediction_class = "real"
       icon = "✅"

    elif label == "Fake News":
       prediction_class = "fake"
       icon = "❌"

    elif label == "Suspicious":
       prediction_class = "suspicious"
       icon = "⚠️"

    else:
       prediction_class = ""
       icon = ""

    return render_template(
    "result.html",
    prediction=label,
    confidence=confidence,
    news=final_text,
    reason=reason,
    sub_label=sub_label,
    prediction_class=prediction_class,
    icon=icon
)

# ================= HISTORY =================

@app.route('/history')
def history():

    if 'user_id' not in session:
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("SELECT * FROM history WHERE user_id=? ORDER BY id DESC", (session['user_id'],))
    data = c.fetchall()

    real_count = sum(1 for i in data if "Real" in i[2])
    fake_count = sum(1 for i in data if "Fake" in i[2])

    conn.close()

    return render_template('history.html', data=data, real_count=real_count, fake_count=fake_count)

# ================= DELETE =================

@app.route('/delete/<int:id>', methods=['POST'])
def delete(id):

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute("DELETE FROM history WHERE id=?", (id,))
    conn.commit()
    conn.close()

    return redirect('/history')

# ================= REGISTER =================

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password'].strip()
        mobile = request.form['mobile'].strip()

        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        try:
            c.execute(
                "INSERT INTO users (name, email, password, mobile) VALUES (?, ?, ?, ?)",
                (name, email, password, mobile)
            )

            conn.commit()
            conn.close()

            # ✅ SUCCESS RESPONSE (IMPORTANT)
            return render_template(
                "register.html",
                success="Account created successfully! Please login."
            )

        except Exception as e:
            conn.close()

            return render_template(
                "register.html",
                msg="Email already exists or error occurred"
            )

    # ✅ VERY IMPORTANT (GET REQUEST)
    return render_template('register.html')
# ================= LOGIN =================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email'].strip().lower()
        password = request.form['password'].strip()

        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        c.execute("SELECT id, name FROM users WHERE email=? AND password=?", (email, password))
        user = c.fetchone()

        conn.close()

        if user:
            session['user'] = user[1]
            session['user_id'] = user[0]
            return redirect('/detect')

        return render_template('login.html', msg="Invalid credentials")

    return render_template('login.html')

# ================= LOGOUT =================

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# ================= RUN =================
@app.route('/profile')
def profile():

    if not session.get('user_id'):
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # USER INFO
    c.execute("SELECT name, email FROM users WHERE id=?", (session['user_id'],))
    user = c.fetchone()

    # HISTORY STATS
    c.execute("SELECT COUNT(*) FROM history WHERE user_id=?", (session['user_id'],))
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM history WHERE result='Real News' AND user_id=?", (session['user_id'],))
    real = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM history WHERE result='Fake News' AND user_id=?", (session['user_id'],))
    fake = c.fetchone()[0]

    conn.close()

    return render_template(
        "profile.html",
        user_name=user[0],
        user_email=user[1],
        total_checks=total,
        real_count=real,
        fake_count=fake
    )

if __name__ == '__main__':
    app.run(debug=True)