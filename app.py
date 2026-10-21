from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from google import genai

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret-before-production")

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Render deploy ku environment variable use pannunga.
# Local test ku terminal la GEMINI_API_KEY set pannunga OR direct key paste pannunga.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

COMMON_AI_RULES = """
Give simple, clear educational health information in plain English.
Do not diagnose with certainty or prescribe medicines or dosages.
Explain general self-care, warning signs, and when to contact a qualified clinician.
For severe or sudden symptoms, advise urgent medical care.
Mention that this information is not a substitute for a medical professional.
Keep the answer concise and use headings and bullet points.
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
    if client is None:
        return "AI service is not configured. Please add GEMINI_API_KEY in your Render environment variables."
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = response.text or "The AI could not generate a response. Please try again."

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

    user_msg = (request.form.get("quick_question") or request.form.get("message") or "").strip()
    if not user_msg:
        return redirect("/ai-chat")

    # Five quick questions use safe, predefined educational responses.
    normalized = user_msg.lower()
    if "fever" in normalized:
        ai_reply = ("GENERAL FEVER GUIDANCE\n"
                    "• Rest and drink fluids.\n"
                    "• If possible, check and record your temperature.\n"
                    "• Seek medical advice if fever is persistent, worsening, or affects a young child or a person with a serious condition.\n"
                    "• Get urgent help for difficulty breathing, confusion, stiff neck, seizures, or severe weakness.\n"
                    "• This is general information, not a diagnosis or prescription.")
    elif "headache" in normalized or "migraine" in normalized:
        ai_reply = ("GENERAL HEADACHE GUIDANCE\n"
                    "• Rest in a quiet place and drink water.\n"
                    "• Take a break from screens and note possible triggers.\n"
                    "• Contact a clinician if headaches keep returning or are getting worse.\n"
                    "• Seek emergency care for a sudden, extremely severe headache or headache with weakness, fainting, confusion, fever with stiff neck, or vision/speech changes.\n"
                    "• This is general information, not a diagnosis or prescription.")
    elif "cold" in normalized or "cough" in normalized or "sneez" in normalized:
        ai_reply = ("GENERAL COLD / COUGH GUIDANCE\n"
                    "• Rest, drink fluids, and consider warm drinks to soothe the throat.\n"
                    "• Avoid smoke and other irritants.\n"
                    "• Seek medical advice if symptoms worsen, last longer than expected, or you have a high/persistent fever.\n"
                    "• Get urgent help for difficulty breathing, chest pain, blue lips, or confusion.\n"
                    "• Ask a clinician or pharmacist before using medicines, especially for children or if you have other conditions.")
    elif "diabetes" in normalized or "blood sugar" in normalized:
        ai_reply = ("GENERAL DIABETES CARE TIPS\n"
                    "• Follow the care plan and medicines prescribed by your clinician.\n"
                    "• Monitor blood glucose as advised and keep a record.\n"
                    "• Eat regular balanced meals, stay active as appropriate, and attend follow-up visits.\n"
                    "• Do not stop or change diabetes medicine without medical advice.\n"
                    "• Seek urgent help for severe confusion, fainting, or other severe symptoms.")
    elif "blood pressure" in normalized or "hypertension" in normalized:
        ai_reply = ("GENERAL BLOOD PRESSURE GUIDANCE\n"
                    "• Measure blood pressure using the correct technique and record results.\n"
                    "• Follow your clinician's advice about food, activity, and prescribed medicine.\n"
                    "• Do not stop or change prescribed medicine on your own.\n"
                    "• If a very high reading occurs with chest pain, breathlessness, weakness, confusion, or severe headache, seek emergency care.\n"
                    "• A clinician should interpret repeated high readings.")
    else:
        prompt = f"""
You are an educational AI health assistant. Do not claim to diagnose or prescribe medicines.
User question or symptoms:
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

            extension = os.path.splitext(filename)[1].lower()
            report_text = ""
            try:
                if extension in (".txt", ".csv"):
                    report_text = open(filepath, "r", encoding="utf-8", errors="ignore").read()[:20000]
                elif extension == ".pdf":
                    from pypdf import PdfReader
                    reader = PdfReader(filepath)
                    report_text = "\n".join((page.extract_text() or "") for page in reader.pages)[:20000]
                else:
                    report_text = "This file type is saved, but automatic text extraction is not supported. Please upload a text-based PDF, TXT, or CSV report."
            except Exception:
                report_text = "The file was uploaded, but its text could not be extracted. Please try a text-based PDF, TXT, or CSV file."

            if report_text.strip() and not report_text.startswith("This file type") and not report_text.startswith("The file was uploaded"):
                summary = ask_ai(f"""
You are an educational medical report explainer. Summarize only what is present in the extracted report text. Do not diagnose or prescribe medicine. Explain that reference ranges depend on the lab and patient context. Highlight any result that appears marked high/low in the report, suggest questions to ask a clinician, and advise urgent care for severe symptoms.

Extracted medical report text:
{report_text}

{COMMON_AI_RULES}
""")
            else:
                summary = report_text or "No readable text was found in this file. Please upload a text-based PDF, TXT, or CSV report."

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
You are an educational symptom-summary assistant, not a prescribing clinician.
Do not generate a prescription, recommend specific medicines, or provide dosages.
Create a concise summary of the symptoms, general non-drug self-care, warning signs, and questions the user can discuss with a licensed clinician.

User symptoms:
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

@app.route("/clear-history", methods=["GET", "POST"])
def clear_history():
    if not logged_in():
        return redirect("/login")
    conn = db()
    cur = conn.cursor()
    cur.execute("DELETE FROM chat_history WHERE user_email=?", (session["email"],))
    conn.commit()
    conn.close()
    return redirect("/ai-chat")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    app.run(debug=True)
