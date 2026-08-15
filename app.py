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
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import pyotp

# App Initialisation
app = Flask(__name__)
app.secret_key = 'mvp-secret'
DB = 'portal.db'
DEV_MODE = True  # Change to False for real use

# --- DATABASE SETUP ---
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def get_current_trainee(conn):
    """Link logged-in auth_user to their trainee record in the user table, matched by email."""
    auth = conn.execute('SELECT email FROM auth_user WHERE username = ?', (session["user"],)).fetchone()
    if not auth:
        return None
    return conn.execute('SELECT * FROM user WHERE email = ?', (auth["email"],)).fetchone()

def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS auth_user (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, otp_secret TEXT NOT NULL);
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
            INSERT INTO user (department_id, email, full_name, role) VALUES (1, 'alice@company.com', 'Alice Johnson', 'admin'), (1, 'bob@company.com', 'Bob Smith', 'learner'), (2, 'carol@company.com', 'Carol White', 'learner'), (2, 'joe@company.com', 'Joe (Admin)', 'admin');
            INSERT INTO scenario (title, attack_type, difficulty, email_subject, email_body, sender_name, sender_email) VALUES ('Urgent Password Reset', 'Credential Harvest', 'easy', 'ACTION REQUIRED: Please click the Phishing link', 'Dear User, please click the below link so I can hack your network.', 'Malicious Hacker', 'hacker@badguy.com'), ('CEO Wire Transfer', 'Business Email Compromise', 'medium', 'Confidential - urgent wire transfer needed', 'Hi, I need you to process an urgent wire transfer of $47,500 to a new vendor before EOD. Keep this confidential.', 'Michael Chen (CEO)', 'mchen@company-corp.net');
            INSERT INTO campaign (name, status, starts_at, ends_at) VALUES ('Q3 Awareness Training', 'active', '2026-04-01', '2026-06-30');
            INSERT INTO campaign_scenario (campaign_id, scenario_id, sequence_order) VALUES (1, 1, 1), (1, 2, 2);
            INSERT INTO user_campaign (user_id, campaign_id, status) VALUES (2, 1, 'enrolled'), (3, 1, 'enrolled'), (4, 1, 'enrolled');
        ''')

    # Insert default login account (auth_user is separate from the trainee "user" table above)
    if conn.execute('SELECT COUNT(*) FROM auth_user').fetchone()[0] == 0:
        conn.execute(
            'INSERT INTO auth_user (username, email, password_hash, otp_secret) VALUES (?, ?, ?, ?)',
            ('joe', 'joe@company.com', generate_password_hash('password123', method='pbkdf2:sha256'), pyotp.random_base32())
        )

    conn.commit()
    conn.close()

init_db()  # Run on import so the schema exists whether started via `python app.py` or `flask run`

# --- AUTHENTICATION ROUTES ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form["username"]  # accepts either a username or an email
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            'SELECT * FROM auth_user WHERE username = ? OR email = ?', (identifier, identifier)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user"] = user["username"]
            return redirect("/otp")
        return "Login failed"

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db()
        existing = conn.execute(
            'SELECT id FROM auth_user WHERE username = ? OR email = ?', (username, email)
        ).fetchone()

        if existing:
            conn.close()
            return "Username or email already registered"

        conn.execute(
            'INSERT INTO auth_user (username, email, password_hash, otp_secret) VALUES (?, ?, ?, ?)',
            (username, email, generate_password_hash(password, method='pbkdf2:sha256'), pyotp.random_base32())
        )

        # Give the new login a matching trainee record, unless one already exists under this email
        try:
            conn.execute(
                'INSERT INTO user (email, full_name, role) VALUES (?, ?, ?)', (email, username, 'learner')
            )
        except sqlite3.IntegrityError:
            pass

        conn.commit()
        conn.close()
        return redirect("/login")

    return render_template("register.html")

@app.route("/otp", methods=["GET", "POST"])
def otp():
    if "user" not in session: return redirect("/login")

    conn = get_db()
    user = conn.execute('SELECT * FROM auth_user WHERE username = ?', (session["user"],)).fetchone()
    conn.close()

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
        
        # --- ETHICAL AI GUARDRAILS ---
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
    conn = get_db()
    rows = conn.execute('''
        SELECT c.*,
            (SELECT COUNT(*) FROM campaign_scenario cs WHERE cs.campaign_id = c.id) AS scenario_count,
            (SELECT COUNT(*) FROM user_campaign uc WHERE uc.campaign_id = c.id) AS enrolled_count,
            (SELECT AVG(uc.score) FROM user_campaign uc WHERE uc.campaign_id = c.id) AS avg_score
        FROM campaign c
        ORDER BY c.id DESC
    ''').fetchall()
    conn.close()
    return render_template('campaigns.html', campaigns=rows)

@app.route('/campaigns/new', methods=['GET', 'POST'])
def new_campaign():
    if "user" not in session: return redirect("/login")
    conn = get_db()

    if request.method == 'POST':
        name = request.form.get('name')
        status = request.form.get('status', 'draft')
        starts_at = request.form.get('starts_at') or None
        ends_at = request.form.get('ends_at') or None
        scenario_ids = request.form.getlist('scenario_ids')

        cur = conn.execute(
            'INSERT INTO campaign (name, status, starts_at, ends_at) VALUES (?, ?, ?, ?)',
            (name, status, starts_at, ends_at)
        )
        campaign_id = cur.lastrowid

        for order, scenario_id in enumerate(scenario_ids, start=1):
            conn.execute(
                'INSERT INTO campaign_scenario (campaign_id, scenario_id, sequence_order) VALUES (?, ?, ?)',
                (campaign_id, scenario_id, order)
            )

        conn.commit()
        conn.close()
        return redirect(url_for('campaign_detail', campaign_id=campaign_id))

    scenarios = conn.execute('SELECT * FROM scenario').fetchall()
    conn.close()
    return render_template('campaign_form.html', scenarios=scenarios)

@app.route('/campaigns/<int:campaign_id>')
def campaign_detail(campaign_id):
    if "user" not in session: return redirect("/login")
    conn = get_db()

    campaign = conn.execute('SELECT * FROM campaign WHERE id = ?', (campaign_id,)).fetchone()
    if campaign is None:
        conn.close()
        return "Campaign not found", 404

    scenarios = conn.execute('''
        SELECT s.*, cs.sequence_order
        FROM campaign_scenario cs JOIN scenario s ON s.id = cs.scenario_id
        WHERE cs.campaign_id = ?
        ORDER BY cs.sequence_order
    ''', (campaign_id,)).fetchall()

    roster = conn.execute('''
        SELECT uc.*, u.full_name, u.email
        FROM user_campaign uc JOIN user u ON u.id = uc.user_id
        WHERE uc.campaign_id = ?
        ORDER BY u.full_name
    ''', (campaign_id,)).fetchall()

    available_users = conn.execute('''
        SELECT * FROM user
        WHERE id NOT IN (SELECT user_id FROM user_campaign WHERE campaign_id = ?)
        ORDER BY full_name
    ''', (campaign_id,)).fetchall()

    conn.close()
    return render_template(
        'campaign_detail.html',
        campaign=campaign, scenarios=scenarios, roster=roster, available_users=available_users
    )

@app.route('/campaigns/<int:campaign_id>/enroll', methods=['POST'])
def enroll_campaign(campaign_id):
    if "user" not in session: return redirect("/login")
    user_id = request.form.get('user_id')

    if user_id:
        conn = get_db()
        existing = conn.execute(
            'SELECT id FROM user_campaign WHERE campaign_id = ? AND user_id = ?', (campaign_id, user_id)
        ).fetchone()
        if not existing:
            conn.execute(
                'INSERT INTO user_campaign (user_id, campaign_id) VALUES (?, ?)', (user_id, campaign_id)
            )
            conn.commit()
        conn.close()

    return redirect(url_for('campaign_detail', campaign_id=campaign_id))

# --- THE SIMULATOR TRAINING LOOP ---
@app.route('/train', methods=['GET', 'POST'])
def train():
    if "user" not in session: return redirect("/login")
    conn = get_db()
    trainee = get_current_trainee(conn)

    if trainee is None:
        conn.close()
        return render_template(
            'train.html', scenario=None,
            message="Your login isn't linked to a trainee profile, so there's nothing to train on yet."
        )

    if request.method == 'POST':
        # 1. Grab the user's choice from the buttons, and which real scenario or enrollment it belongs to
        action = request.form.get('action')  # 'phishing' or 'safe'
        user_campaign_id = request.form.get('user_campaign_id')
        campaign_scenario_id = request.form.get('campaign_scenario_id')

        # 2. Evaluate if they were correct
        correct = (action == 'phishing')
        flagged = 1 if action == 'phishing' else 0
        points = 10 if correct else 0

        # 3. Store the response and add its score to the enrollment's running total
        conn.execute('''
            INSERT INTO user_response (user_campaign_id, campaign_scenario_id, action, flagged_as_phishing, score)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_campaign_id, campaign_scenario_id, action, flagged, points))
        conn.execute(
            'UPDATE user_campaign SET score = score + ? WHERE id = ?', (points, user_campaign_id)
        )

        # 4. Mark the enrollment complete once every scenario in its campaign has been answered
        campaign_id = conn.execute(
            'SELECT campaign_id FROM user_campaign WHERE id = ?', (user_campaign_id,)
        ).fetchone()['campaign_id']
        total_scenarios = conn.execute(
            'SELECT COUNT(*) FROM campaign_scenario WHERE campaign_id = ?', (campaign_id,)
        ).fetchone()[0]
        answered_scenarios = conn.execute(
            'SELECT COUNT(DISTINCT campaign_scenario_id) FROM user_response WHERE user_campaign_id = ?',
            (user_campaign_id,)
        ).fetchone()[0]
        if answered_scenarios >= total_scenarios:
            conn.execute(
                "UPDATE user_campaign SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
                (user_campaign_id,)
            )

        conn.commit()
        conn.close()

        # 5. Show the feedback screen
        return render_template('feedback.html', correct=correct, action=action)

    # If GET request: find the trainee's next unanswered scenario from an active campaign they're enrolled in
    next_scenario = conn.execute('''
        SELECT s.*, cs.id AS campaign_scenario_id, uc.id AS user_campaign_id
        FROM user_campaign uc
        JOIN campaign c ON c.id = uc.campaign_id
        JOIN campaign_scenario cs ON cs.campaign_id = uc.campaign_id
        JOIN scenario s ON s.id = cs.scenario_id
        WHERE uc.user_id = ?
          AND c.status = 'active'
          AND uc.status = 'enrolled'
          AND cs.id NOT IN (
              SELECT campaign_scenario_id FROM user_response WHERE user_campaign_id = uc.id
          )
        ORDER BY uc.enrolled_at, cs.sequence_order
        LIMIT 1
    ''', (trainee['id'],)).fetchone()
    conn.close()

    if next_scenario is None:
        return render_template(
            'train.html', scenario=None,
            message="No active training assigned right now — check back once you're enrolled in a campaign."
        )

    return render_template('train.html', scenario=next_scenario, message=None)

if __name__ == '__main__':
    conn = get_db()
    joe_secret = conn.execute('SELECT otp_secret FROM auth_user WHERE username = ?', ('joe',)).fetchone()[0]
    conn.close()
    print("-----------------------------------------")
    print(f"JOE'S SECRET FOR AUTHENTICATOR: {joe_secret}")
    print("-----------------------------------------")
    app.run(debug=True)