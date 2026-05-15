import os
from google import genai
from dotenv import load_dotenv

# Load the secret key and configure the AI
load_dotenv()

# Initialize the new genai client
ai_client = None
if os.getenv("GEMINI_API_KEY"):
    ai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import pyotp

# App Initialisation
app = Flask(__name__)
app.secret_key = 'mvp-secret'
DB = 'portal.db'
DEV_MODE = True  # Change to False for real use

# Fake database for Auth 
users_auth = {
    "joe": {
        "password": "password123",
        "otp_secret": pyotp.random_base32()
    }
}

# --- DATABASE SETUP ---
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS department (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT);
        CREATE TABLE IF NOT EXISTS user (id INTEGER PRIMARY KEY AUTOINCREMENT, department_id INTEGER REFERENCES department(id), email TEXT NOT NULL UNIQUE, full_name TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'learner');
        CREATE TABLE IF NOT EXISTS scenario (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, attack_type TEXT NOT NULL, difficulty TEXT NOT NULL, email_subject TEXT NOT NULL, email_body TEXT NOT NULL, sender_name TEXT NOT NULL, sender_email TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS campaign (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft', starts_at TEXT, ends_at TEXT);
        CREATE TABLE IF NOT EXISTS campaign_scenario (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER REFERENCES campaign(id), scenario_id INTEGER REFERENCES scenario(id), sequence_order INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS user_campaign (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES user(id), campaign_id INTEGER REFERENCES campaign(id), status TEXT NOT NULL DEFAULT 'enrolled', score INTEGER DEFAULT 0, enrolled_at TEXT DEFAULT CURRENT_TIMESTAMP, completed_at TEXT);
        CREATE TABLE IF NOT EXISTS user_response (id INTEGER PRIMARY KEY AUTOINCREMENT, user_campaign_id INTEGER REFERENCES user_campaign(id), campaign_scenario_id INTEGER REFERENCES campaign_scenario(id), action TEXT NOT NULL, flagged_as_phishing INTEGER DEFAULT 0, score INTEGER DEFAULT 0, responded_at TEXT DEFAULT CURRENT_TIMESTAMP);
    ''')
    
    # Build database schema if empty
    if conn.execute('SELECT COUNT(*) FROM department').fetchone()[0] == 0:
        conn.executescript('''
            INSERT INTO department (name, description) VALUES ('Finance', 'Finance and accounting'), ('Engineering', 'Software development'), ('HR', 'Human resources');
            INSERT INTO user (department_id, email, full_name, role) VALUES (1, 'alice@company.com', 'Alice Johnson', 'admin'), (1, 'bob@company.com', 'Bob Smith', 'learner'), (2, 'carol@company.com', 'Carol White', 'learner');
            INSERT INTO scenario (title, attack_type, difficulty, email_subject, email_body, sender_name, sender_email) VALUES ('Urgent Password Reset', 'Credential Harvest', 'easy', 'ACTION REQUIRED: Please click the Phishing link', 'Dear User, please click the below link so I can hack your network.', 'Malicious Hacker', 'hacker@badguy.com'), ('CEO Wire Transfer', 'Business Email Compromise', 'medium', 'Confidential - urgent wire transfer needed', 'Hi, I need you to process an urgent wire transfer of $47,500 to a new vendor before EOD. Keep this confidential.', 'Michael Chen (CEO)', 'mchen@company-corp.net');
            INSERT INTO campaign (name, status, starts_at, ends_at) VALUES ('Q3 Awareness Training', 'active', '2026-04-01', '2026-06-30');
            INSERT INTO campaign_scenario (campaign_id, scenario_id, sequence_order) VALUES (1, 1, 1), (1, 2, 2);
            INSERT INTO user_campaign (user_id, campaign_id, status) VALUES (2, 1, 'enrolled'), (3, 1, 'enrolled');
        ''')
    conn.commit()
    conn.close()

# --- AUTHENTICATION ROUTES ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = users_auth.get(username)

        if user and user["password"] == password:
            session["user"] = username
            return redirect("/otp")
        return "Login failed"

    return render_template("login.html")

@app.route("/otp", methods=["GET", "POST"])
def otp():
    if "user" not in session: return redirect("/login")
        
    user = users_auth[session["user"]]
    totp = pyotp.TOTP(user["otp_secret"])

    if DEV_MODE: print("DEV OTP:", totp.now())  # Shows OTP in terminal

    if request.method == "POST":
        code = request.form["otp"]
        # DEV bypass or real verification
        if (DEV_MODE and code == "000000") or totp.verify(code):
            return redirect("/") # Success! Send to Dashboard
        return "Invalid OTP"

    return render_template("otp.html")

# --- DASHBOARD & PAGES ---
@app.route('/')
def index():
    if "user" not in session: return redirect("/login")
        
    conn = get_db()
    
    # 1. Calculate raw response numbers
    total_responses = conn.execute('SELECT COUNT(*) FROM user_response').fetchone()[0]
    successes = conn.execute("SELECT COUNT(*) FROM user_response WHERE action='phishing'").fetchone()[0]
    failures = total_responses - successes
    
    # 2. Calculate percentages
    success_rate = f"{(successes / total_responses * 100):.1f}%" if total_responses > 0 else "0%"
    failure_rate = f"{(failures / total_responses * 100):.1f}%" if total_responses > 0 else "0%"

    # 3. Package the stats for the frontend
    stats = {
        'users': conn.execute('SELECT COUNT(*) FROM user').fetchone()[0],
        'campaigns': conn.execute('SELECT COUNT(*) FROM campaign').fetchone()[0],
        'scenarios': conn.execute('SELECT COUNT(*) FROM scenario').fetchone()[0],
        'responses': total_responses,
        'successes': successes,
        'failures': failures,
        'success_rate': success_rate,
        'failure_rate': failure_rate
    }
    conn.close()
    return render_template('index.html', stats=stats)

@app.route('/users')
def users():
    if "user" not in session: return redirect("/login")
    conn = get_db()
    rows = conn.execute('''
        SELECT u.*, d.name as dept_name
        FROM user u LEFT JOIN department d ON u.department_id = d.id
    ''').fetchall()
    conn.close()
    return render_template('users.html', users=rows)

@app.route('/users/new', methods=['GET', 'POST'])
def new_user():
    if "user" not in session: return redirect("/login")
    conn = get_db()
    
    if request.method == 'POST':
        full_name, email, department_id, role = request.form.get('full_name'), request.form.get('email'), request.form.get('department_id'), request.form.get('role')
        if department_id == "": department_id = None
            
        try:
            conn.execute('INSERT INTO user (full_name, email, department_id, role) VALUES (?, ?, ?, ?)', (full_name, email, department_id, role))
            conn.commit()
        except sqlite3.IntegrityError:
            print("Error: Email already exists!")
        finally:
            conn.close()
        return redirect('/users')
        
    departments = conn.execute('SELECT id, name FROM department').fetchall()
    conn.close()
    return render_template('user_form.html', departments=departments)

@app.route('/departments')
def departments():
    if "user" not in session: return redirect("/login")
    return render_template('departments.html')

@app.route('/scenarios', methods=['GET', 'POST'])
def scenarios():
    if "user" not in session: return redirect("/login")

    conn = get_db()
    generated_email = None

    if request.method == 'POST':
        scenario_type = request.form.get('scenario_type') 
        
        # --- THE ETHICAL AI GUARDRAILS ---
        prompt = f"""
        You are an educational cybersecurity AI acting as a backend engine for a phishing simulator.
        Your task is to generate a safe, simulated phishing email for a corporate training environment.
        
        Scenario Type Requested: {scenario_type}
        
        STRICT ETHICAL GUARDRAILS:
        1. DO NOT include any real malicious URLs, IP addresses, or tracking pixels. Use the exact text "[SIMULATED_LINK_HERE]" instead.
        2. DO NOT include actual malware payloads, scripts, or weaponized attachments.
        3. DO NOT use real company names. Use generic terms like 'Acme Corp', 'IT Helpdesk', or 'Finance Dept'.
        4. Keep the email under 300 words.
        
        Output format MUST be exactly:
        SUBJECT: <the subject line>
        BODY: <the email body>
        """
        
        try:
            # Call the free Gemini 2.5 Flash model 
            response = ai_client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            generated_text = response.text
            
            # Parse the Subject and Body to save to the database
            subject = "AI Generated Subject"
            body = generated_text
            if "SUBJECT:" in generated_text and "BODY:" in generated_text:
                subject = generated_text.split("SUBJECT:")[1].split("BODY:")[0].strip()
                body = generated_text.split("BODY:")[1].strip()

            # Insert the new AI scenario into the database schema
            conn.execute('''
                INSERT INTO scenario (title, attack_type, difficulty, email_subject, email_body, sender_name, sender_email)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (f"AI Gen: {scenario_type[:15]}", scenario_type, "medium", subject, body, "IT Security", "security@acme-corp.internal"))
            conn.commit()
            
            generated_email = generated_text
        except Exception as e:
            generated_email = f"Error connecting to AI: {str(e)}"
            
    # Fetch all scenarios to display
    existing_scenarios = conn.execute('SELECT * FROM scenario').fetchall()
    conn.close()
    
    return render_template('scenarios.html', scenarios=existing_scenarios, generated_email=generated_email)

@app.route('/campaigns')
def campaigns():
    if "user" not in session: return redirect("/login")
    return render_template('campaigns.html')

# --- THE SIMULATOR TRAINING LOOP ---
@app.route('/train', methods=['GET', 'POST'])
def train():
    if "user" not in session: return redirect("/login")
    conn = get_db()
    
    if request.method == 'POST':
        # 1. Grab the user's choice from the buttons
        action = request.form.get('action') # 'phishing' or 'safe'
        scenario_id = request.form.get('scenario_id')
        
        # 2. Evaluate if they were correct
        correct = (action == 'phishing')
        flagged = 1 if action == 'phishing' else 0
        
        # 3. Store the data (Satisfies the Flowchart & ERD)
        conn.execute('''
            INSERT INTO user_response (user_campaign_id, campaign_scenario_id, action, flagged_as_phishing)
            VALUES (1, 1, ?, ?)
        ''', (action, flagged))
        conn.commit()
        conn.close()
        
        # 4. Show the feedback screen
        return render_template('feedback.html', correct=correct, action=action)

    # If GET request: Pick a random scenario from the database to display
    scenario = conn.execute('SELECT * FROM scenario ORDER BY RANDOM() LIMIT 1').fetchone()
    conn.close()
    
    return render_template('train.html', scenario=scenario)

if __name__ == '__main__':
    print("-----------------------------------------")
    print(f"JOE'S SECRET FOR AUTHENTICATOR: {users_auth['joe']['otp_secret']}") 
    print("-----------------------------------------")
    init_db()
    app.run(debug=True)