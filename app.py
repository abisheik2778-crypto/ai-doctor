from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from google import genai

app = Flask(__name__)
app.secret_key = "ai_doctor_secret_key"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Render deploy ku environment variable use pannunga.
# Local test ku terminal la GEMINI_API_KEY set pannunga OR direct key paste pannunga.
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "AQ.Ab8RN6KUN07ahPrDPVNpCItmcivX62WygBU2dEBbwnbWhd5SFw"))

COMMON_AI_RULES = """
Give answer in SIMPLE ENGLISH.

Use this format:

AI HEALTH RESPONSE

Possible Disease:
• disease 1
• disease 2

Suggested Medicine Category:
• Mild fever → Paracetamol type medicine may help
• Cold / sneezing → Antihistamine type medicine may help
• Cough → Cough syrup type medicine may help
• Acidity → Antacid type medicine may help
• Loose motion → ORS and hydration may help

Home Care:
• care 1
• care 2

Recommended Tests:
• test 1
• test 2

Warning Signs:
• warning 1
• warning 2

Doctor Advice:
• Consult a real doctor before taking medicine.
• This AI gives educational guidance only.

Rules:
• Keep answer short
• Keep answer line by line
• Use bullet points
• No markdown
• No stars
• No exact dosage
"""

def db():
    return sqlite3.connect("database.db")

def init_db():
    conn = db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS chat_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        user_msg TEXT,
        ai_reply TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS appointments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        patient_name TEXT,
        doctor_name TEXT,
        date TEXT,
        time TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS reports(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT,
        filename TEXT,
        summary TEXT,
        uploaded_at TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

def ask_ai(prompt):
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = response.text

        text = text.replace("Possible Disease:", "\nPossible Disease:")
        text = text.replace("Suggested Medicine Category:", "\nSuggested Medicine Category:")
        text = text.replace("Common Medicine Type:", "\nCommon Medicine Type:")
        text = text.replace("Home Care:", "\nHome Care:")
        text = text.replace("Recommended Tests:", "\nRecommended Tests:")
        text = text.replace("Warning Signs:", "\nWarning Signs:")
        text = text.replace("Doctor Advice:", "\nDoctor Advice:")

        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")

        return text.strip()

    except Exception as e:
        return "AI service error. Check API key or internet connection."

def logged_in():
    return "user" in session and "email" in session

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    error = ""

    if request.method == "POST":
        try:
            conn = db()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users(name,email,password) VALUES(?,?,?)",
                (
                    request.form["name"],
                    request.form["email"],
                    request.form["password"]
                )
            )
            conn.commit()
            conn.close()
            return redirect("/login")

        except:
            error = "Email already exists"

    return render_template("register.html", error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":
        conn = db()
        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (
                request.form["email"],
                request.form["password"]
            )
        )

        user = cur.fetchone()
        conn.close()

        if user:
            session["user"] = user[1]
            session["email"] = user[2]
            return redirect("/dashboard")
        else:
            error = "Invalid Email or Password"

    return render_template("login.html", error=error)

@app.route("/dashboard")
def dashboard():
    if not logged_in():
        return redirect("/login")

    return render_template("dashboard.html", name=session["user"])

@app.route("/ai-chat")
def ai_chat():
    if not logged_in():
        return redirect("/login")

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_msg, ai_reply, created_at FROM chat_history WHERE user_email=? ORDER BY id DESC",
        (session["email"],)
    )

    chats = cur.fetchall()
    conn.close()

    return render_template("ai_chat.html", name=session["user"], chats=chats)

@app.route("/chat", methods=["POST"])
def chat():
    if not logged_in():
        return redirect("/login")

    user_msg = request.form["message"]

    prompt = f"""
You are an AI Doctor Assistant.

User Symptoms:
{user_msg}

{COMMON_AI_RULES}
"""

    ai_reply = ask_ai(prompt)

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO chat_history(user_email,user_msg,ai_reply,created_at) VALUES(?,?,?,?)",
        (
            session["email"],
            user_msg,
            ai_reply,
            datetime.now().strftime("%d-%m-%Y %I:%M %p")
        )
    )

    conn.commit()
    conn.close()

    return redirect("/ai-chat")

@app.route("/report", methods=["GET", "POST"])
def report():
    if not logged_in():
        return redirect("/login")

    message = ""

    if request.method == "POST":
        file = request.files["report"]

        if file.filename != "":
            filename = secure_filename(file.filename)

            filepath = os.path.join(
                app.config["UPLOAD_FOLDER"],
                filename
            )

            file.save(filepath)

            summary = ask_ai(f"""
You are an AI Medical Report Analyzer.

Medical Report:
{filename}

{COMMON_AI_RULES}
""")

            conn = db()
            cur = conn.cursor()

            cur.execute(
                "INSERT INTO reports(user_email,filename,summary,uploaded_at) VALUES(?,?,?,?)",
                (
                    session["email"],
                    filename,
                    summary,
                    datetime.now().strftime("%d-%m-%Y %I:%M %p")
                )
            )

            conn.commit()
            conn.close()

            message = "Report uploaded successfully!"

    conn = db()
    cur = conn.cursor()

    cur.execute(
        "SELECT filename, summary, uploaded_at FROM reports WHERE user_email=? ORDER BY id DESC",
        (session["email"],)
    )

    reports = cur.fetchall()
    conn.close()

    return render_template(
        "report.html",
        name=session["user"],
        reports=reports,
        message=message
    )

@app.route("/appointments", methods=["GET", "POST"])
def appointments():
    if not logged_in():
        return redirect("/login")

    message = ""

    if request.method == "POST":
        conn = db()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO appointments(
                user_email,
                patient_name,
                doctor_name,
                date,
                time,
                created_at
            )
            VALUES(?,?,?,?,?,?)
            """,
            (
                session["email"],
                request.form["patient_name"],
                request.form["doctor_name"],
                request.form["date"],
                request.form["time"],
                datetime.now().strftime("%d-%m-%Y %I:%M %p")
            )
        )

        conn.commit()
        conn.close()

        message = "Appointment booked successfully!"

    conn = db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT patient_name, doctor_name, date, time, created_at
        FROM appointments
        WHERE user_email=?
        ORDER BY id DESC
        """,
        (session["email"],)
    )

    appointments_data = cur.fetchall()
    conn.close()

    return render_template(
        "appointments.html",
        name=session["user"],
        appointments=appointments_data,
        message=message
    )

@app.route("/bmi", methods=["GET", "POST"])
def bmi():
    if not logged_in():
        return redirect("/login")

    result = ""
    status = ""

    if request.method == "POST":
        height = float(request.form["height"]) / 100
        weight = float(request.form["weight"])

        bmi_value = weight / (height * height)
        result = round(bmi_value, 2)

        if bmi_value < 18.5:
            status = "Underweight"
        elif bmi_value < 25:
            status = "Normal / Healthy"
        elif bmi_value < 30:
            status = "Overweight"
        else:
            status = "Obese"

    return render_template(
        "bmi.html",
        name=session["user"],
        result=result,
        status=status
    )

@app.route("/profile")
def profile():
    if not logged_in():
        return redirect("/login")

    return render_template(
        "profile.html",
        name=session["user"],
        email=session["email"]
    )

@app.route("/tips")
def tips():
    if not logged_in():
        return redirect("/login")

    tips_data = [
        "Drink enough water every day.",
        "Sleep 7 to 8 hours daily.",
        "Eat healthy food and avoid junk food.",
        "Do walking or light exercise daily.",
        "Wash hands before eating.",
        "Avoid stress and take short breaks.",
        "Consult a doctor for serious symptoms."
    ]

    return render_template(
        "tips.html",
        name=session["user"],
        tips=tips_data
    )

@app.route("/emergency")
def emergency():
    if not logged_in():
        return redirect("/login")

    return render_template(
        "emergency.html",
        name=session["user"]
    )

@app.route("/prescription", methods=["GET", "POST"])
def prescription():
    if not logged_in():
        return redirect("/login")

    output = ""

    if request.method == "POST":
        symptom = request.form["symptom"]

        prompt = f"""
You are an AI Prescription Assistant.

User Symptoms:
{symptom}

{COMMON_AI_RULES}
"""

        output = ask_ai(prompt)

    return render_template(
        "prescription.html",
        name=session["user"],
        output=output
    )

@app.route("/doctor-panel")
def doctor_panel():
    if not logged_in():
        return redirect("/login")

    conn = db()
    cur = conn.cursor()

    cur.execute("""
    SELECT patient_name, doctor_name, date, time
    FROM appointments
    ORDER BY id DESC
    """)

    appointments = cur.fetchall()

    cur.execute("""
    SELECT filename, uploaded_at
    FROM reports
    ORDER BY id DESC
    """)

    reports = cur.fetchall()

    conn.close()

    return render_template(
        "doctor_panel.html",
        name=session["user"],
        appointments=appointments,
        reports=reports
    )

@app.route("/clear-history")
def clear_history():

    conn = sqlite3.connect("database.db")
    cur = conn.cursor()

    cur.execute("DELETE FROM chat_history")

    conn.commit()
    conn.close()

    return redirect("/ai-chat")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    app.run(debug=True)
