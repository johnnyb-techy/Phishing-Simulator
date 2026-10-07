from google import genai
from dotenv import load_dotenv
import os
import secrets
import time
import random
import re
import html

# Load the secret key and configure the AI
load_dotenv()

# Initialize the new genai client
ai_client = None
if os.getenv("GEMINI_API_KEY"):
    ai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
   
 # Study areas used to create different training scenarios
STUDY_AREAS = [
    "Information Technology",
    "Computer Science",
    "Nursing",
    "Education",
    "Business",
    "Accounting",
    "Psychology",
    "Social Work",
    "Engineering",
    "Agriculture",
    "Environmental Science",
    "Health Science",
    "Law",
    "Communications",
    "Creative Arts",
    "Sport & Exercise Science"
]

# Different scenario ideas for each study area
SCENARIO_CONTEXTS = {
    "Information Technology": [
        "password reset",
        "software licence renewal",
        "cloud storage warning",
        "IT support request",
        "account security alert"
    ],

    "Computer Science": [
        "coding assignment submission",
        "Git repository access",
        "developer account warning",
        "cloud computing access",
        "group project invitation"
    ],

    "Nursing": [
        "clinical placement notification",
        "placement roster update",
        "training requirement",
        "health documentation request",
        "supervisor communication"
    ],

    "Education": [
        "teaching placement",
        "school placement update",
        "lesson plan submission",
        "assessment notification",
        "teaching resource access"
    ],

    "Business": [
        "internship opportunity",
        "group project",
        "invoice notification",
        "student payment",
        "business competition"
    ],

    "Accounting": [
        "tax workshop",
        "financial report submission",
        "invoice approval",
        "student payment",
        "internship notification"
    ],

    "Psychology": [
        "research participation",
        "placement notification",
        "survey invitation",
        "assessment update",
        "student support communication"
    ],

    "Social Work": [
        "community placement",
        "case study submission",
        "placement supervisor message",
        "training requirement",
        "community organisation notification"
    ],

    "Engineering": [
        "project submission",
        "laboratory access",
        "software licence",
        "group design project",
        "industry placement"
    ],

    "Agriculture": [
        "field placement",
        "farm visit",
        "research survey",
        "equipment booking",
        "industry placement"
    ],

    "Environmental Science": [
        "fieldwork notification",
        "research project",
        "laboratory booking",
        "equipment access",
        "field trip update"
    ],

    "Health Science": [
        "placement requirement",
        "training notification",
        "laboratory session",
        "student health documentation",
        "assessment submission"
    ],

    "Law": [
        "legal placement",
        "case study submission",
        "research database access",
        "student society notification",
        "assessment update"
    ],

    "Communications": [
        "media project",
        "group assignment",
        "portfolio submission",
        "event invitation",
        "internship opportunity"
    ],

    "Creative Arts": [
        "portfolio submission",
        "performance booking",
        "gallery event",
        "project collaboration",
        "assessment upload"
    ],

    "Sport & Exercise Science": [
        "practical session",
        "placement notification",
        "training event",
        "fitness assessment",
        "sports club communication"
    ]
}

# Different question styles the AI can create
QUESTION_TYPES = [
    "True or False",
    "Multiple Choice",
    "Phishing or Legitimate",
    "What Would You Do?",
    "Trick Question"
]

# Random difficulty for each training scenario
DIFFICULTIES = [
    "Easy",
    "Medium",
    "Hard"
]

# Slightly more phishing scenarios than legitimate ones
CLASSIFICATIONS = [
    "Phishing",
    "Phishing",
    "Phishing",
    "Legitimate",
    "Legitimate"
]

# Randomly choose the settings for a new training scenario
def generate_parameters(allowed_study_areas=None):

    # Use department study areas when provided
    # Otherwise use the full list as a fallback
    study_area_choices = allowed_study_areas or STUDY_AREAS

    # Pick a random study area
    study_area = random.choice(study_area_choices)

    # Pick a scenario that belongs to that study area
    scenario_context = random.choice(SCENARIO_CONTEXTS[study_area])

    # Randomly choose the rest of the training settings
    question_type = random.choice(QUESTION_TYPES)
    difficulty = random.choice(DIFFICULTIES)
    classification = random.choice(CLASSIFICATIONS)

    # Package everything together so Gemini can use it later
    return {
        "study_area": study_area,
        "scenario_context": scenario_context,
        "question_type": question_type,
        "difficulty": difficulty,
        "classification": classification
    }


from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3

# App Initialisation
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "mvp-secret")  # set SECRET_KEY in .env outside local development
DB = 'portal.db'
DEV_MODE = False  # Development mode kept disabled for normal testing

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

# Check whether the currently logged-in user is an admin
def is_admin(conn):
    if "user" not in session:
        return False

    current_user = get_current_trainee(conn)

    if current_user is None:
        return False

    return current_user["role"] == "admin"

# Redirect to the login page unless the user has completed login and OTP
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

# Make the logged-in username and admin flag available to every template
@app.context_processor
def inject_current_user():
    if "user" not in session:
        return {"current_user": None, "current_is_admin": False}
    conn = get_db()
    admin = is_admin(conn)
    conn.close()
    return {"current_user": session["user"], "current_is_admin": admin}


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS auth_user (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, otp_secret TEXT NOT NULL);
       CREATE TABLE IF NOT EXISTS department (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT);

CREATE TABLE IF NOT EXISTS department_study_area (
    department_id INTEGER NOT NULL,
    study_area TEXT NOT NULL,
    PRIMARY KEY (department_id, study_area),
    FOREIGN KEY (department_id) REFERENCES department(id)
);

CREATE TABLE IF NOT EXISTS user (id INTEGER PRIMARY KEY AUTOINCREMENT, department_id INTEGER REFERENCES department(id), email TEXT NOT NULL UNIQUE, full_name TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'learner');
        CREATE TABLE IF NOT EXISTS scenario (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, attack_type TEXT NOT NULL, difficulty TEXT NOT NULL, email_subject TEXT NOT NULL, email_body TEXT NOT NULL, sender_name TEXT NOT NULL, sender_email TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS campaign (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft', starts_at TEXT, ends_at TEXT);
        CREATE TABLE IF NOT EXISTS campaign_scenario (id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER REFERENCES campaign(id), scenario_id INTEGER REFERENCES scenario(id), sequence_order INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS user_campaign (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES user(id), campaign_id INTEGER REFERENCES campaign(id), status TEXT NOT NULL DEFAULT 'enrolled', score INTEGER DEFAULT 0, enrolled_at TEXT DEFAULT CURRENT_TIMESTAMP, completed_at TEXT);
        CREATE TABLE IF NOT EXISTS user_response (id INTEGER PRIMARY KEY AUTOINCREMENT, user_campaign_id INTEGER REFERENCES user_campaign(id), campaign_scenario_id INTEGER REFERENCES campaign_scenario(id), action TEXT NOT NULL, flagged_as_phishing INTEGER DEFAULT 0, score INTEGER DEFAULT 0, responded_at TEXT DEFAULT CURRENT_TIMESTAMP);
    ''')
           
        # Add training question fields to older databases
    scenario_columns = [
        row["name"]
        for row in conn.execute("PRAGMA table_info(scenario)").fetchall()
    ]

    new_columns = {
        "question_type": "TEXT",
        "question": "TEXT",
        "option_a": "TEXT",
        "option_b": "TEXT",
        "option_c": "TEXT",
        "option_d": "TEXT",
        "correct_answer": "TEXT",
        "explanation": "TEXT"
    }

        # Scenario migration
    for column, column_type in new_columns.items():
        if column not in scenario_columns:
            conn.execute(
                f"ALTER TABLE scenario ADD COLUMN {column} {column_type}"
            )


    # Add a job title field to older user databases
    user_columns = [
        row["name"]
        for row in conn.execute("PRAGMA table_info(user)").fetchall()
    ]

    if "job_title" not in user_columns:
        conn.execute(
            "ALTER TABLE user ADD COLUMN job_title TEXT"
        )


   # Add a target department to older campaign databases
    campaign_columns = [
        row["name"]
        for row in conn.execute("PRAGMA table_info(campaign)").fetchall()
    ]

    if "department_id" not in campaign_columns:
        conn.execute(
            "ALTER TABLE campaign ADD COLUMN department_id INTEGER"
        )


    # Build database schema if empty
    if conn.execute('SELECT COUNT(*) FROM department').fetchone()[0] == 0:
        conn.executescript('''
            INSERT INTO department (name, description)
            VALUES
                ('Finance', 'Finance and accounting'),
                ('Engineering', 'Software development'),
                ('HR', 'Human resources');

            INSERT INTO user (department_id, email, full_name, role)
            VALUES
                (1, 'alice@company.com', 'Alice Johnson', 'admin'),
                (1, 'bob@company.com', 'Bob Smith', 'learner'),
                (2, 'carol@company.com', 'Carol White', 'learner'),
                (2, 'joe@company.com', 'Joe (Admin)', 'admin');

            INSERT INTO scenario
                (title, attack_type, difficulty, email_subject, email_body, sender_name, sender_email)
            VALUES
                (
                    'Urgent Password Reset',
                    'Credential Harvest',
                    'easy',
                    'ACTION REQUIRED: Please click the Phishing link',
                    'Dear User, please click the below link so I can hack your network.',
                    'Malicious Hacker',
                    'hacker@badguy.com'
                ),
                (
                    'CEO Wire Transfer',
                    'Business Email Compromise',
                    'medium',
                    'Confidential - urgent wire transfer needed',
                    'Hi, I need you to process an urgent wire transfer of $47,500 to a new vendor before EOD. Keep this confidential.',
                    'Michael Chen (CEO)',
                    'mchen@company-corp.net'
                );

            INSERT INTO campaign (name, status, starts_at, ends_at)
            VALUES ('Q3 Awareness Training', 'active', '2026-04-01', '2026-06-30');

            INSERT INTO campaign_scenario
                (campaign_id, scenario_id, sequence_order)
            VALUES
                (1, 1, 1),
                (1, 2, 2);

            INSERT INTO user_campaign
                (user_id, campaign_id, status)
            VALUES
                (2, 1, 'enrolled'),
                (3, 1, 'enrolled'),
                (4, 1, 'enrolled');
        ''')

    # Insert default login account
    if conn.execute('SELECT COUNT(*) FROM auth_user').fetchone()[0] == 0:
        conn.execute(
            'INSERT INTO auth_user (username, email, password_hash, otp_secret) VALUES (?, ?, ?, ?)',
            (
                'joe',
                'joe@company.com',
                generate_password_hash(
                    'password123',
                    method='pbkdf2:sha256'
                ),
                'unused'
            )
        )

    conn.commit()
    conn.close()

init_db()  # Run on import so the schema exists whether started via `python app.py` or `flask run`

# --- AUTHENTICATION ROUTES ---
@app.route("/login", methods=["GET", "POST"])
def login():
    # Already logged in - skip straight to the dashboard
    if "user" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        identifier = request.form.get("username", "").strip()  # accepts either a username or an email
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute(
            'SELECT * FROM auth_user WHERE username = ? OR email = ?',
            (identifier, identifier)
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):

            # Start from a fresh session so no earlier login state carries over
            session.clear()

            # Password is correct, but user still needs to complete OTP
            session["pending_user"] = user["username"]

            # Generate a secure 6-digit OTP
            otp_code = str(secrets.randbelow(900000) + 100000)

            # Temporarily store the OTP
            session["otp_code"] = otp_code

            # Record when the OTP was created
            session["otp_created"] = time.time()

            return redirect(url_for("otp"))

        flash("Incorrect username/email or password.")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if "user" in session:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("Username, email and password are all required.")
            return render_template("register.html")

        conn = get_db()
        existing = conn.execute(
            'SELECT id FROM auth_user WHERE username = ? OR email = ?', (username, email)
        ).fetchone()

        if existing:
            conn.close()
            flash("Username or email already registered.")
            return render_template("register.html")

        conn.execute(
            'INSERT INTO auth_user (username, email, password_hash, otp_secret) VALUES (?, ?, ?, ?)',
            (username, email, generate_password_hash(password, method='pbkdf2:sha256'), 'unused')
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
        flash("Account created. Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/otp", methods=["GET", "POST"])
def otp():
    # User must have passed the password stage and have an OTP waiting
    if "pending_user" not in session or "otp_code" not in session or "otp_created" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        code = request.form.get("otp", "").strip()

        # Check whether the OTP has expired (5 minutes)
        if time.time() - session["otp_created"] > 300:
            session.clear()
            flash("Your code expired. Please log in again.")
            return redirect(url_for("login"))

        # Check whether the entered OTP is correct
        if secrets.compare_digest(code, session["otp_code"]):

            # OTP passed - user is now fully logged in; drop the temporary OTP information
            username = session["pending_user"]
            session.clear()
            session["user"] = username

            return redirect(url_for("index"))

        flash("Incorrect code. Please try again.")

    return render_template("otp.html", otp_code=session["otp_code"])

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You have been logged out.")
    return redirect(url_for("login"))


# --- DASHBOARD & PAGES ---
@app.route('/')
@login_required
def index():
    conn = get_db()
    
    # 1. Calculate raw response numbers
    total_responses = conn.execute('SELECT COUNT(*) FROM user_response').fetchone()[0]
    successes = conn.execute("SELECT COUNT(*) FROM user_response WHERE score > 0").fetchone()[0]
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
@login_required
def users():
    conn = get_db()

    if not is_admin(conn):
        conn.close()
        return "Access denied. Admin privileges are required.", 403
    
    
    rows = conn.execute('''
        SELECT u.*, d.name as dept_name
        FROM user u LEFT JOIN department d ON u.department_id = d.id
    ''').fetchall()
    
    conn.close()
    return render_template('users.html', users=rows)

@app.route('/users/new', methods=['GET', 'POST'])
@login_required
def new_user():
    conn = get_db()

    if not is_admin(conn):
        conn.close()
        return "Access denied. Admin privileges are required.", 403

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        job_title = request.form.get('job_title')
        department_id = request.form.get('department_id')
        role = request.form.get('role')

        if department_id == "":
            department_id = None

        try:
            conn.execute(
                '''
                INSERT INTO user
                (full_name, email, job_title, department_id, role)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (full_name, email, job_title, department_id, role)
            )

            conn.commit()

        except sqlite3.IntegrityError:
            print("Error: Email already exists!")

        finally:
            conn.close()

        return redirect('/users')

    departments = conn.execute(
        'SELECT id, name FROM department'
    ).fetchall()

    conn.close()

    return render_template(
        'user_form.html',
        departments=departments
    )
# Edit an existing user's details
@app.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    conn = get_db()
    
    #Stops non Admins from Editing Users.
    if not is_admin(conn):
        conn.close()
        return "Access denied. Admin privileges are required.", 403

    # Find the user being edited
    edit_user = conn.execute(
        'SELECT * FROM user WHERE id = ?',
        (user_id,)
    ).fetchone()

    if edit_user is None:
        conn.close()
        return "User not found", 404

    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email')
        job_title = request.form.get('job_title')
        department_id = request.form.get('department_id')
        role = request.form.get('role')

        if department_id == "":
            department_id = None

        try:
            conn.execute('''
                UPDATE user
                SET full_name = ?,
                    email = ?,
                    job_title = ?,
                    department_id = ?,
                    role = ?
                WHERE id = ?
            ''', (
                full_name,
                email,
                job_title,
                department_id,
                role,
                user_id
            ))

            conn.commit()

        except sqlite3.IntegrityError:
            conn.close()
            return "That email is already being used by another user."

        conn.close()
        return redirect(url_for('users'))

    departments = conn.execute(
        'SELECT id, name FROM department ORDER BY name'
    ).fetchall()

    conn.close()

    return render_template(
        'user_edit.html',
        edit_user=edit_user,
        departments=departments
    )

# Delete a user and their training data
@app.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    conn = get_db()
    
    # Deleting User Protection.
    if not is_admin(conn):
        conn.close()
        return "Access denied. Admin privileges are required.", 403

    # Delete training responses belonging to this user
    conn.execute('''
        DELETE FROM user_response
        WHERE user_campaign_id IN (
            SELECT id
            FROM user_campaign
            WHERE user_id = ?
        )
    ''', (user_id,))

    # Delete the user's campaign enrolments
    conn.execute(
        'DELETE FROM user_campaign WHERE user_id = ?',
        (user_id,)
    )

    # Delete the user
    conn.execute(
        'DELETE FROM user WHERE id = ?',
        (user_id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for('users'))

@app.route('/departments')
@login_required
def departments():
    conn = get_db()

    if not is_admin(conn):
        conn.close()
        return "Access denied. Admin privileges are required.", 403

    rows = conn.execute(
        'SELECT * FROM department ORDER BY name'
    ).fetchall()

    conn.close()

    return render_template(
        'departments.html',
        departments=rows
    )
    
# Create a new department
@app.route('/departments/new', methods=['GET', 'POST'])
@login_required
def new_department():
    conn = get_db()

    # Only admins can create departments
    if not is_admin(conn):
        conn.close()
        return "Access denied. Admin privileges are required.", 403

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')

        try:
            conn.execute(
                '''
                INSERT INTO department (name, description)
                VALUES (?, ?)
                ''',
                (name, description)
            )

            conn.commit()

        except sqlite3.IntegrityError:
            conn.close()
            return "That department already exists."

        conn.close()
        return redirect(url_for('departments'))

    conn.close()

    return render_template('departments_form.html')

# Edit an existing department
@app.route('/departments/<int:department_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_department(department_id):
    conn = get_db()

    # Only admins can edit departments
    if not is_admin(conn):
        conn.close()
        return "Access denied. Admin privileges are required.", 403

    department = conn.execute(
        'SELECT * FROM department WHERE id = ?',
        (department_id,)
    ).fetchone()

    if department is None:
        conn.close()
        return "Department not found", 404

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        selected_study_areas = request.form.getlist('study_areas')

        try:
            conn.execute(
                '''
                UPDATE department
                SET name = ?, description = ?
                WHERE id = ?
                ''',
                (name, description, department_id)
            )

            # Remove the old study area links
            conn.execute(
                'DELETE FROM department_study_area WHERE department_id = ?',
                (department_id,)
            )

            # Save the newly selected study areas
            for study_area in selected_study_areas:
                conn.execute(
                    '''
                    INSERT INTO department_study_area (department_id, study_area)
                    VALUES (?, ?)
                    ''',
                    (department_id, study_area)
                )

            conn.commit()

        except sqlite3.IntegrityError:
            conn.close()
            return "That department name is already being used."

        conn.close()
        return redirect(url_for('departments'))

    # Get the study areas already linked to this department
    selected_study_areas = [
        row["study_area"]
        for row in conn.execute(
            '''
            SELECT study_area
            FROM department_study_area
            WHERE department_id = ?
            ''',
            (department_id,)
        ).fetchall()
    ]

    conn.close()

    return render_template(
        'departments_edit.html',
        department=department,
        study_areas=STUDY_AREAS,
        selected_study_areas=selected_study_areas
    )
    
# Delete a department if no users are assigned to it
@app.route('/departments/<int:department_id>/delete', methods=['POST'])
@login_required
def delete_department(department_id):
    conn = get_db()

    # Only admins can delete departments
    if not is_admin(conn):
        conn.close()
        return "Access denied. Admin privileges are required.", 403

    department = conn.execute(
        'SELECT * FROM department WHERE id = ?',
        (department_id,)
    ).fetchone()

    if department is None:
        conn.close()
        return "Department not found", 404

    # Check whether any users still belong to this department
    user_count = conn.execute(
        'SELECT COUNT(*) FROM user WHERE department_id = ?',
        (department_id,)
    ).fetchone()[0]

    if user_count > 0:
        conn.close()
        return "This department cannot be deleted because users are still assigned to it.", 400

    conn.execute(
        'DELETE FROM department WHERE id = ?',
        (department_id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for('departments'))

@app.route('/scenarios', methods=['GET', 'POST'])
@login_required
def scenarios():
    conn = get_db()
    
    # Only admins can manage and generate scenarios
    if not is_admin(conn):
        conn.close()
        return "Access denied. Admin privileges are required.", 403
    
    generated_email = None

    # Only show departments that actually have users assigned
    departments = conn.execute('''
        SELECT d.id, d.name
        FROM department d
        WHERE EXISTS (
            SELECT 1
            FROM user u
            WHERE u.department_id = d.id
        )
        ORDER BY d.name
    ''').fetchall()

    if request.method == 'POST':

        # Get the department selected by the admin
        department_id = request.form.get('department_id')

        # Make sure the selected department actually has users
        user_count = conn.execute(
            '''
            SELECT COUNT(*)
            FROM user
            WHERE department_id = ?
            ''',
            (department_id,)
        ).fetchone()[0]

        if user_count == 0:
            conn.close()
            return "No users are assigned to this department.", 400

        # Get the study areas linked to the selected department
        department_study_areas = [
            row["study_area"]
            for row in conn.execute(
                '''
                SELECT study_area
                FROM department_study_area
                WHERE department_id = ?
                ''',
                (department_id,)
            ).fetchall()
        ]

        # Make sure the department has training areas configured
        if not department_study_areas:
            conn.close()
            return "This department has no training study areas assigned.", 400

        # Generate using only this department's study areas
        parameters = generate_parameters(department_study_areas)

        study_area = parameters["study_area"]
        scenario_context = parameters["scenario_context"]
        question_type = parameters["question_type"]
        difficulty = parameters["difficulty"]
        classification = parameters["classification"]

        # --- ETHICAL AI GUARDRAILS ---
        prompt = f"""
        You are an educational cybersecurity AI creating a safe training exercise
        for university students.

        Generate a fictional cybersecurity awareness scenario using these settings:

        Study Area: {study_area}
        Scenario Context: {scenario_context}
        Question Type: {question_type}
        Difficulty: {difficulty}
        Classification: {classification}

        TRAINING RULES:
        1. The scenario must be suitable for university cybersecurity awareness training.
        2. Do not use real organisations, real people, real URLs, credentials, malware,
           tracking links, or instructions for wrongdoing.
        3. If the classification is Phishing, create a clearly fictional training
           scenario containing suspicious indicators that a student can identify.
        4. If the classification is Legitimate, create a normal fictional university
           communication without deceptive or malicious behaviour.
        5. Match the scenario to the selected study area and context.
        6. Match the complexity to the selected difficulty.
        7. Make the exercise suitable for the selected question type.
        8. Keep the scenario concise and educational.

        Output format MUST be exactly:

        SUBJECT: <fictional subject line>
        BODY: <fictional training message>
        QUESTION: <question for the student>
        OPTION_A: <first answer choice>
        OPTION_B: <second answer choice>
        OPTION_C: <third answer choice>
        OPTION_D: <fourth answer choice>
        ANSWER: <A, B, C, or D>
        EXPLANATION: <short explanation of why the answer is correct>
        """

        try:
            # Call the Gemini Flash model
            response = ai_client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt
            )

            generated_text = response.text

            # Clean up the AI response before using it
            generated_text = html.unescape(generated_text)

            # Replace Markdown website links with a safe placeholder
            generated_text = re.sub(
                r'\[([^\]]+)\]\(https?://[^)]+\)',
                r'\1 [SIMULATED LINK]',
                generated_text
            )

            # Replace normal http:// or https:// links
            generated_text = re.sub(
                r'https?://[^\s]+',
                '[SIMULATED LINK]',
                generated_text
            )

            # Replace bare website domains without http:// or https://
            generated_text = re.sub(
                r'\b(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?:/[^\s]*)?',
                '[SIMULATED LINK]',
                generated_text
            )

            # Start with fallback values in case Gemini changes its format
            subject = "AI Generated Training Scenario"
            body = generated_text

            # Set fallback values for the training question
            question = ""
            option_a = ""
            option_b = ""
            option_c = ""
            option_d = ""
            correct_answer = ""
            explanation = ""
            
            
                    # Separate the subject and body from the training question
            if "SUBJECT:" in generated_text and "BODY:" in generated_text:
                subject = generated_text.split("SUBJECT:", 1)[1].split("BODY:", 1)[0].strip()

                body_section = generated_text.split("BODY:", 1)[1]

                if "QUESTION:" in body_section:
                    body = body_section.split("QUESTION:", 1)[0].strip()
                else:
                    body = body_section.strip()

                # Separate the training question, answer choices and explanation
                if all(label in generated_text for label in [
                    "QUESTION:",
                    "OPTION_A:",
                    "OPTION_B:",
                    "OPTION_C:",
                    "OPTION_D:",
                    "ANSWER:",
                    "EXPLANATION:"
                ]):
                    question = generated_text.split("QUESTION:", 1)[1].split("OPTION_A:", 1)[0].strip()
                    option_a = generated_text.split("OPTION_A:", 1)[1].split("OPTION_B:", 1)[0].strip()
                    option_b = generated_text.split("OPTION_B:", 1)[1].split("OPTION_C:", 1)[0].strip()
                    option_c = generated_text.split("OPTION_C:", 1)[1].split("OPTION_D:", 1)[0].strip()
                    option_d = generated_text.split("OPTION_D:", 1)[1].split("ANSWER:", 1)[0].strip()
                    correct_answer = generated_text.split("ANSWER:", 1)[1].split("EXPLANATION:", 1)[0].strip()
                    explanation = generated_text.split("EXPLANATION:", 1)[1].strip()


            # Save the randomly generated training scenario
            conn.execute('''
                INSERT INTO scenario
                (
                    title,
                    attack_type,
                    difficulty,
                    email_subject,
                    email_body,
                    sender_name,
                    sender_email,
                    question_type,
                    question,
                    option_a,
                    option_b,
                    option_c,
                    option_d,
                    correct_answer,
                    explanation
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                f"{study_area}: {scenario_context}",
                classification,
                difficulty,
                subject,
                body,
                "University Training",
                "training@simulated-university.internal",
                question_type,
                question,
                option_a,
                option_b,
                option_c,
                option_d,
                correct_answer,
                explanation
            ))
            
            conn.commit()
            generated_email = generated_text

        except Exception as e:
            # Keep the real error in the terminal for debugging
            print(f"AI generation error: {e}")

        # Show the user a simple message instead
            generated_email = (
            "AI scenario generation is temporarily unavailable. "
            "Please try again later."
        )
            
    # Fetch all scenarios to display
    existing_scenarios = conn.execute('SELECT * FROM scenario').fetchall()
    conn.close()

    return render_template(
    'scenarios.html',
    scenarios=existing_scenarios,
    generated_email=generated_email,
    departments=departments
)
    
#Campaigns page to show all campaigns and their details
@app.route('/campaigns')
@login_required
def campaigns():
    conn = get_db()
    current_user = get_current_trainee(conn)

    # Admins can see every campaign
    if is_admin(conn):
        rows = conn.execute('''
            SELECT c.*,
                (SELECT COUNT(*) FROM campaign_scenario cs
                 WHERE cs.campaign_id = c.id) AS scenario_count,

                (SELECT COUNT(*) FROM user_campaign uc
                 WHERE uc.campaign_id = c.id) AS enrolled_count,

                (SELECT AVG(uc.score) FROM user_campaign uc
                 WHERE uc.campaign_id = c.id) AS avg_score

            FROM campaign c
            ORDER BY c.id DESC
        ''').fetchall()

    # Learners only see campaigns they are enrolled in
    elif current_user is not None:
        rows = conn.execute('''
            SELECT c.*,
                (SELECT COUNT(*) FROM campaign_scenario cs
                 WHERE cs.campaign_id = c.id) AS scenario_count,

                (SELECT COUNT(*) FROM user_campaign uc
                 WHERE uc.campaign_id = c.id) AS enrolled_count,

                (SELECT AVG(uc.score) FROM user_campaign uc
                 WHERE uc.campaign_id = c.id) AS avg_score

            FROM campaign c
            JOIN user_campaign uc
                ON uc.campaign_id = c.id
            WHERE uc.user_id = ?
            ORDER BY c.id DESC
        ''', (current_user["id"],)).fetchall()

    else:
        rows = []

    conn.close()

    return render_template(
        'campaigns.html',
        campaigns=rows
    )

@app.route('/campaigns/new', methods=['GET', 'POST'])
@login_required
def new_campaign():
    conn = get_db()

    # Only admins can create campaigns
    if not is_admin(conn):
        conn.close()
        return "Access denied. Admin privileges are required.", 403
    
    # Only show departments that have users assigned
    departments = conn.execute('''
        SELECT d.id, d.name
        FROM department d
        WHERE EXISTS (
            SELECT 1
            FROM user u
            WHERE u.department_id = d.id
        )
        ORDER BY d.name
    ''').fetchall()
    
    if request.method == 'POST':
        name = request.form.get('name')
        department_id = request.form.get('department_id')
          # Make sure the selected department actually has users
        user_count = conn.execute(
            '''
            SELECT COUNT(*)
            FROM user
            WHERE department_id = ?
            ''',
            (department_id,)
        ).fetchone()[0]

        if user_count == 0:
            conn.close()
            return "No users are assigned to this department.", 400
       # New campaigns always begin as a draft
        status = 'draft'
        starts_at = request.form.get('starts_at') or None
        ends_at = request.form.get('ends_at') or None
        scenario_ids = request.form.getlist('scenario_ids')

        # Create the campaign and save its target department
        cur = conn.execute(
            '''
            INSERT INTO campaign
            (name, status, starts_at, ends_at, department_id)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (name, status, starts_at, ends_at, department_id)
        )

        campaign_id = cur.lastrowid

        # Add the selected scenarios to the new campaign
        for order, scenario_id in enumerate(scenario_ids, start=1):
            conn.execute(
                '''
                INSERT INTO campaign_scenario
                (campaign_id, scenario_id, sequence_order)
                VALUES (?, ?, ?)
                ''',
                (campaign_id, scenario_id, order)
            )

        conn.commit()
        conn.close()

        return redirect(
            url_for('campaign_detail', campaign_id=campaign_id)
        )
    scenarios = conn.execute('SELECT * FROM scenario').fetchall()
    conn.close()
    return render_template(
    'campaign_form.html',
    scenarios=scenarios,
    departments=departments
)

@app.route('/campaigns/<int:campaign_id>')
@login_required
def campaign_detail(campaign_id):
    conn = get_db()
    
    current_user = get_current_trainee(conn)

    # Make sure the logged-in account is linked to a user
    if current_user is None:
        conn.close()
        return "User profile not found.", 404

    # Learners can only view campaigns they are enrolled in
    if not is_admin(conn):
        enrolled = conn.execute(
            '''
            SELECT id
            FROM user_campaign
            WHERE user_id = ?
              AND campaign_id = ?
            ''',
            (current_user["id"], campaign_id)
        ).fetchone()

        if enrolled is None:
            conn.close()
            return "Access denied. You are not enrolled in this campaign.", 403

    # Get the campaign and the name of its target department
    campaign = conn.execute('''
        SELECT c.*, d.name AS department_name
        FROM campaign c
        LEFT JOIN department d
            ON d.id = c.department_id
        WHERE c.id = ?
    ''', (campaign_id,)).fetchone()
    # Stop here if the campaign no longer exists
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

       # Only show available users from this campaign's target department
    available_users = conn.execute('''
        SELECT *
        FROM user
        WHERE department_id = ?
          AND id NOT IN (
              SELECT user_id
              FROM user_campaign
              WHERE campaign_id = ?
          )
        ORDER BY full_name
    ''', (
        campaign["department_id"],
        campaign_id
    )).fetchall()
    
        # Remember whether this user is an admin before closing the database
    admin_view = is_admin(conn)

    conn.close()

    return render_template(
        'campaign_detail.html',
        campaign=campaign,
        scenarios=scenarios,
        roster=roster,
        available_users=available_users,
        admin_view=admin_view
    )
    
#Enrolling in Campaigns - Only Admins can manually enrol users into campaigns.
@app.route('/campaigns/<int:campaign_id>/enroll', methods=['POST'])
@login_required
def enroll_campaign(campaign_id):
    user_id = request.form.get('user_id')
    conn = get_db()

    # Only admins can manually enrol users
    if not is_admin(conn):
        conn.close()
        return "Access denied. Admin privileges are required.", 403

    conn.close()
    
    if user_id:
        conn = get_db()

        # Get the campaign's target department
        campaign = conn.execute(
            'SELECT department_id FROM campaign WHERE id = ?',
            (campaign_id,)
        ).fetchone()

        # Get the selected user's department
        selected_user = conn.execute(
            'SELECT department_id FROM user WHERE id = ?',
            (user_id,)
        ).fetchone()

        # Only allow users from the campaign's target department
        if (
            campaign is None
            or selected_user is None
            or campaign["department_id"] != selected_user["department_id"]
        ):
            conn.close()
            return "This user does not belong to the campaign's target department.", 400

        existing = conn.execute(
            '''
            SELECT id
            FROM user_campaign
            WHERE campaign_id = ? AND user_id = ?
            ''',
            (campaign_id, user_id)
        ).fetchone()

        if not existing:
            conn.execute(
                '''
                INSERT INTO user_campaign (user_id, campaign_id)
                VALUES (?, ?)
                ''',
                (user_id, campaign_id)
            )
            conn.commit()

        conn.close()

    return redirect(url_for('campaign_detail', campaign_id=campaign_id))

# Start the specific campaign selected by the user
@app.route('/campaign/<int:campaign_id>/start-training', methods=['POST'])
@login_required
def start_campaign_training(campaign_id):
    conn = get_db()
    trainee = get_current_trainee(conn)

    if trainee is None:
        conn.close()
        return redirect(url_for('campaigns'))

    enrolled = conn.execute('''
        SELECT id
        FROM user_campaign
        WHERE user_id = ?
          AND campaign_id = ?
    ''', (trainee['id'], campaign_id)).fetchone()

    conn.close()

    if enrolled is None:
        return redirect(url_for('campaign_detail', campaign_id=campaign_id))

    # Remember exactly which campaign the user selected
    session['training_campaign_id'] = campaign_id

    return redirect(url_for('train'))

# Allow a learner to retry a completed campaign
@app.route('/campaign/<int:campaign_id>/retry', methods=['POST'])
@login_required
def retry_campaign_training(campaign_id):
    conn = get_db()
    trainee = get_current_trainee(conn)

    if trainee is None:
        conn.close()
        return redirect(url_for('campaigns'))

    # Find this learner's enrolment in the selected campaign
    enrollment = conn.execute('''
        SELECT id
        FROM user_campaign
        WHERE user_id = ?
          AND campaign_id = ?
    ''', (trainee["id"], campaign_id)).fetchone()

    if enrollment is None:
        conn.close()
        return "You are not enrolled in this campaign.", 403

    user_campaign_id = enrollment["id"]

    # Remove the learner's previous answers for this campaign
    conn.execute(
        'DELETE FROM user_response WHERE user_campaign_id = ?',
        (user_campaign_id,)
    )

    # Reset their campaign progress and score
    conn.execute('''
        UPDATE user_campaign
        SET status = 'enrolled',
            score = 0,
            completed_at = NULL
        WHERE id = ?
    ''', (user_campaign_id,))

    conn.commit()
    conn.close()

    # Start this campaign again
    session["training_campaign_id"] = campaign_id

    return redirect(url_for('train'))


# --- THE SIMULATOR TRAINING LOOP ---

# Change the status of an existing campaign
@app.route('/campaign/<int:campaign_id>/status', methods=['POST'])
@login_required
def update_campaign_status(campaign_id):
    conn = get_db()

    # Only admins can change campaign status
    if not is_admin(conn):
        conn.close()
        return "Access denied. Admin privileges are required.", 403

    conn.close()

    new_status = request.form.get('status')

    # Only allow the campaign statuses used by the portal
    if new_status not in ['draft', 'active', 'completed']:
        return redirect(url_for('campaign_detail', campaign_id=campaign_id))

    conn = get_db()
    
    # If the campaign is being activated, prepare its department users
    if new_status == 'active':

        campaign = conn.execute(
            '''
            SELECT department_id
            FROM campaign
            WHERE id = ?
            ''',
            (campaign_id,)
        ).fetchone()

        # Campaign must have a target department
        if campaign is None or campaign["department_id"] is None:
            conn.close()
            return "This campaign does not have a target department.", 400

        # Make sure the target department still has users
        user_count = conn.execute(
            '''
            SELECT COUNT(*)
            FROM user
            WHERE department_id = ?
            ''',
            (campaign["department_id"],)
        ).fetchone()[0]

        if user_count == 0:
            conn.close()
            return "This campaign cannot be activated because its department has no users.", 400
            # Enrol all users from the target department
        conn.execute(
            '''
            INSERT INTO user_campaign (user_id, campaign_id)
            SELECT u.id, ?
            FROM user u
            WHERE u.department_id = ?
              AND NOT EXISTS (
                  SELECT 1
                  FROM user_campaign uc
                  WHERE uc.user_id = u.id
                    AND uc.campaign_id = ?
              )
            ''',
            (
                campaign_id,
                campaign["department_id"],
                campaign_id
            )
        )

    # Update the campaign status after the activation checks
    conn.execute(
        'UPDATE campaign SET status = ? WHERE id = ?',
        (new_status, campaign_id)
    )

    conn.commit()
    conn.close()

    return redirect(url_for('campaign_detail', campaign_id=campaign_id))

# Permanently delete a scenario and its campaign connections
@app.route('/scenario/<int:scenario_id>/delete', methods=['POST'])
@login_required
def delete_scenario(scenario_id):
    conn = get_db()
    
    # Only admins can permanently delete scenarios
    if not is_admin(conn):
        conn.close()
        return "Access denied. Admin privileges are required.", 403

    # Delete responses connected to this scenario through campaigns
    conn.execute('''
        DELETE FROM user_response
        WHERE campaign_scenario_id IN (
            SELECT id
            FROM campaign_scenario
            WHERE scenario_id = ?
        )
    ''', (scenario_id,))

    # Remove the scenario from any campaigns using it
    conn.execute('''
        DELETE FROM campaign_scenario
        WHERE scenario_id = ?
    ''', (scenario_id,))

    # Permanently delete the scenario itself
    conn.execute('''
        DELETE FROM scenario
        WHERE id = ?
    ''', (scenario_id,))

    conn.commit()
    conn.close()

    return redirect(url_for('scenarios'))

# Remove a scenario from a campaign without deleting the scenario itself
@app.route('/campaign/<int:campaign_id>/scenario/<int:scenario_id>/remove', methods=['POST'])
@login_required
def remove_campaign_scenario(campaign_id, scenario_id):
    conn = get_db()
    
    # Only admins can remove scenarios from campaigns
    if not is_admin(conn):
        conn.close()
        return "Access denied. Admin privileges are required.", 403

    # Remove only the connection between this campaign and scenario
    conn.execute('''
        DELETE FROM campaign_scenario
        WHERE campaign_id = ?
          AND scenario_id = ?
    ''', (campaign_id, scenario_id))

    conn.commit()
    conn.close()

    return redirect(url_for('campaign_detail', campaign_id=campaign_id))

# Delete a campaign and its campaign-specific training data
@app.route('/campaign/<int:campaign_id>/delete', methods=['POST'])
@login_required
def delete_campaign(campaign_id):
    conn = get_db()
    # Only admins can delete campaigns
    if not is_admin(conn):
        conn.close()
        return "Access denied. Admin privileges are required.", 403

    # Delete responses connected to this campaign
    conn.execute('''
        DELETE FROM user_response
        WHERE user_campaign_id IN (
            SELECT id
            FROM user_campaign
            WHERE campaign_id = ?
        )
        OR campaign_scenario_id IN (
            SELECT id
            FROM campaign_scenario
            WHERE campaign_id = ?
        )
    ''', (campaign_id, campaign_id))

    # Delete campaign enrolments
    conn.execute(
        'DELETE FROM user_campaign WHERE campaign_id = ?',
        (campaign_id,)
    )

    # Remove scenarios from the campaign, but keep the scenarios themselves
    conn.execute(
        'DELETE FROM campaign_scenario WHERE campaign_id = ?',
        (campaign_id,)
    )

    # Delete the campaign
    conn.execute(
        'DELETE FROM campaign WHERE id = ?',
        (campaign_id,)
    )

    conn.commit()
    conn.close()

    # Forget the selected campaign if this was the one being trained
    if session.get('training_campaign_id') == campaign_id:
        session.pop('training_campaign_id', None)

    return redirect(url_for('campaigns'))

@app.route('/train', methods=['GET', 'POST'])
@login_required
def train():
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

        # 2. Get the correct answer for this training scenario
        answer_row = conn.execute('''
            SELECT s.correct_answer, s.attack_type, s.explanation
            FROM campaign_scenario cs
            JOIN scenario s ON s.id = cs.scenario_id
            WHERE cs.id = ?
        ''', (campaign_scenario_id,)).fetchone()

        # Make sure the scenario has a valid answer before checking the user's choice
        correct = (
            answer_row is not None
            and action is not None
            and answer_row["correct_answer"] is not None
            and action.strip().upper() == answer_row["correct_answer"].strip().upper()
            )

       # The new A-D training system uses the score to track correct answers
        flagged = 0

        # Give 10 points for a correct answer
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
        return render_template(
            'feedback.html',
            correct=correct,
            action=action,
            correct_answer=answer_row["correct_answer"],
            explanation=answer_row["explanation"]
        )

     # If GET request: use the campaign the user deliberately selected
    selected_campaign_id = session.get('training_campaign_id')

    # If no campaign has been selected, send the user to the campaign list
    if selected_campaign_id is None:
        conn.close()
        return redirect(url_for('campaigns'))

    # Find the next unanswered scenario from the selected campaign only
    next_scenario = conn.execute('''
        SELECT s.*, cs.id AS campaign_scenario_id, uc.id AS user_campaign_id
        FROM user_campaign uc
        JOIN campaign c ON c.id = uc.campaign_id
        JOIN campaign_scenario cs ON cs.campaign_id = uc.campaign_id
        JOIN scenario s ON s.id = cs.scenario_id
        WHERE uc.user_id = ?
          AND uc.campaign_id = ?
          AND c.status = 'active'
          AND uc.status = 'enrolled'
          AND cs.id NOT IN (
              SELECT campaign_scenario_id
              FROM user_response
              WHERE user_campaign_id = uc.id
          )
        ORDER BY cs.sequence_order
        LIMIT 1
    ''', (trainee['id'], selected_campaign_id)).fetchone()
    conn.close()

    if next_scenario is None:
        return render_template(
            'train.html', scenario=None,
            message="No active training assigned right now — check back once you're enrolled in a campaign."
        )

    return render_template('train.html', scenario=next_scenario, message=None)

if __name__ == '__main__':
    app.run(debug=True)
