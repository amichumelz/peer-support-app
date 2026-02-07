import re
import csv
import io
import os
import random 
import string 
import json
import smtplib
import cloudinary
import cloudinary.uploader
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template_string, request, redirect, url_for, session, flash, make_response
from datetime import datetime
import mysql.connector
from mysql.connector import Error
from datetime import datetime

# initialize Flask application
app = Flask(__name__)
app.secret_key = 'digital_peer_support_secret'

# ==========================================
# DATABASE CONFIGURATION
# ==========================================

db_config = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'user': os.environ.get('DB_USER', 'root'),
    'password': os.environ.get('DB_PASSWORD', '211521'),
    'database': os.environ.get('DB_NAME', 'peer_support_db'),
    'port': int(os.environ.get('DB_PORT', 3306)) 
}

cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
    secure = True
)

# ==========================================
# EMAIL CONFIGURATION
# ==========================================
SMTP_SERVER = "smtp.gmail.com"  # Google's SMTP server
SMTP_PORT = 587                 # TLS Port
SENDER_EMAIL = "fatinshamirah212@gmail.com" 
SENDER_PASSWORD = "vwowfvevwnjonkcu" # App Pass 

# ==========================================
# UPDATED CONFIG & HELPERS
# ==========================================

# Dynamic Configuration (In-memory for this demo)
CONFIG = {
    # --- 1. Gamification Keys (Used for System Earn Points) ---
    'points_checkin': 5, 
    'points_post': 5,
    'points_comment': 2,
    'points_like': 1,

    # --- 2. Safety Score Keys (Used for Admin/Restrictions) ---
    # Positive Contributions (Green)
    'score_post': 5,
    'score_helpful': 10,
    'score_support': 15,
    
    # Violations (Red)
    'penalty_removal': 15,
    'penalty_harassment': 30,
    'penalty_severe': 50,
    
    # Thresholds
    'restriction_threshold': 60,
    'max_score': 100
}

app.config['UPLOAD_FOLDER'] = 'static/uploads'
# Ensure folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 
    'mp4', 'mp3', 'mov', 'mpeg', 'mpg', 
    'doc', 'docx', 'pptx', 'xls', 'xlsx'
}

#getting the file format: right split 1 time, getting the .blablabla 
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def update_student_score(student_id, amount, action_type="System Action"):
    """
    Gamification/Reputation System (points column):
    - Starts at 100.
    - Controlled by actions (Post/Comment/Like) and Penalties.
    - Daily Limit of 10 points for positive actions.
    - Used for User Restriction logic.
    """
    conn = get_db_connection()
    if not conn: return
    cursor = conn.cursor(dictionary=True)
    
    # 1. Get current Gamification Points
    cursor.execute("SELECT points FROM Student WHERE student_id = %s", (student_id,))
    res = cursor.fetchone()
    if not res: 
        conn.close()
        return

    current_points = res['points']
    actual_change = amount
    
    # 2. Check Daily Limit for REWARDS (Positive points only)
    if amount > 0:
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Sum positive points earned TODAY from ScoreTransaction
        cursor.execute("""
            SELECT SUM(points_change) as daily_total 
            FROM ScoreTransaction 
            WHERE student_id = %s 
              AND DATE(transaction_date) = %s 
              AND points_change > 0
        """, (student_id, today))
        
        daily_res = cursor.fetchone()
        daily_earned = daily_res['daily_total'] if daily_res and daily_res['daily_total'] else 0
        
        # Hardcoded limit or dynamic config
        DAILY_LIMIT = 10 
        
        if daily_earned >= DAILY_LIMIT:
            print(f"Daily limit ({DAILY_LIMIT}) reached for Student {student_id}.")
            actual_change = 0 
        elif daily_earned + amount > DAILY_LIMIT:
            actual_change = DAILY_LIMIT - daily_earned

    # 3. Calculate New Score (Clamp 0-100)
    new_points = current_points + actual_change
    
    # Use dynamic Max Score from Config
    if new_points > CONFIG['max_score']: new_points = CONFIG['max_score']
    if new_points < 0: new_points = 0

    # 4. Update ONLY the 'points' column
    cursor.execute("UPDATE Student SET points = %s WHERE student_id = %s", (new_points, student_id))
    
    # 5. Log transaction to ScoreTransaction
    if actual_change != 0: 
        cursor.execute("""
            INSERT INTO ScoreTransaction (student_id, action_type, points_change, resulting_score) 
            VALUES (%s, %s, %s, %s)
        """, (student_id, action_type, actual_change, new_points))

    conn.commit()
    conn.close()
    return new_points

# Template Library (Kept in memory as it's static data)
PLAN_TEMPLATES = {
    'anxiety': {
        'title': 'Anxiety Management Protocol',
        'goals': 'Reduce panic attack frequency to < 1/week. Improve sleep quality.',
        'strategies': '1. 4-7-8 Breathing Technique\n2. Progressive Muscle Relaxation\n3. Daily Mood Journaling',
        'timeline': '4 Weeks'
    },
    'academic': {
        'title': 'Academic Recovery Plan',
        'goals': 'Submit all overdue assignments. Attend 80% of classes.',
        'strategies': '1. Pomodoro Study Technique\n2. Peer Tutoring Sessions\n3. Weekly Planner Review',
        'timeline': 'Semester End'
    }
}

def get_db_connection():
    try:
        # We add ssl_disabled=False to satisfy Aiven's security requirement
        conn = mysql.connector.connect(**db_config, ssl_disabled=False)
        return conn
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None
    
def query_db(query, args=(), one=False):
    conn = get_db_connection()
    if not conn: return None
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, args)
    result = cursor.fetchall()
    conn.close()
    return (result[0] if result else None) if one else result

def execute_db(query, args=()):
    conn = get_db_connection()
    if not conn: return None
    cursor = conn.cursor()
    try:
        cursor.execute(query, args)
        conn.commit()
        last_id = cursor.lastrowid
        conn.close()
        return last_id
    except Error as e:
        print(f"DB Execution Error: {e}")
        conn.close()
        return None

# --- USER HYDRATION HELPER ---
# Converts SQL rows back into the dictionary structure the UI expects
def get_user_by_id(account_id):
    if not account_id: return None
    
    # 1. Get Base Account
    account = query_db("SELECT * FROM Account WHERE account_id = %s", (account_id,), one=True)
    if not account: return None
    
    user_data = {
        'id': account['account_id'],
        'name': '', # To be filled
        'role': account['role'],
        'username': account['username'],
        'password': account['password'],
        'is_active': bool(account['is_active']),
        # Default fields to prevent UI errors
        'points': 0, 'level': 1, 'score': 100, 'friends': [], 'interests': [], 'caseload': [],
        'program': '', 'bio': '', 'violations': 0, 'specialization': '',
        'avatar': 'https://api.dicebear.com/7.x/identicon/svg?seed=' + account['username']
    }

    # 2. Get Role Specific Data
    if account['role'] == 'student':
        student = query_db("SELECT * FROM Student WHERE account_id = %s", (account_id,), one=True)
        if student:
            user_data.update({
                'student_id': student['student_id'],
                'name': student['full_name'],
                'program': student['program'],
                'points': student['points'],
                'level': 1 + (student['points'] // 50),
                'score': student['score_percentage'],
                'bio': student['bio'],
                'violations': student['violations'],
                'avatar': student['avatar_url'] if student['avatar_url'] else 'https://api.dicebear.com/7.x/avataaars/svg?seed=' + student['full_name'],
                'interests': student['interests'].split(',') if student['interests'] else []
            })
            # Fetch Friends (Account IDs)
            # Fetch Friends (Account IDs) - Added DISTINCT to prevent duplicates
            friends_sql = """
                SELECT DISTINCT a.account_id 
                FROM Friendship f
                JOIN Student s ON (s.student_id = f.student_id_1 OR s.student_id = f.student_id_2)
                JOIN Account a ON s.account_id = a.account_id
                WHERE (f.student_id_1 = %s OR f.student_id_2 = %s) 
                AND f.status = 'Accepted' 
                AND s.student_id != %s
            """
            friends = query_db(friends_sql, (user_data['student_id'], user_data['student_id'], user_data['student_id']))
            user_data['friends'] = [f['account_id'] for f in friends]

    elif account['role'] == 'counselor':
        counselor = query_db("SELECT * FROM Counselor WHERE account_id = %s", (account_id,), one=True)
        if counselor:
            user_data.update({
                'counselor_id': counselor['counselor_id'],
                'name': counselor['full_name'],
                'specialization': counselor['specialization']
            })
            # Fetch Caseload (Account IDs of students)
            caseload = query_db("""
                SELECT s.account_id 
                FROM Assignment a
                JOIN Student s ON a.student_id = s.student_id
                WHERE a.counselor_id = %s AND a.status = 'Accepted'
            """, (user_data['counselor_id'],))
            user_data['caseload'] = [c['account_id'] for c in caseload]

    elif account['role'] == 'admin':
        admin = query_db("SELECT * FROM Admin WHERE account_id = %s", (account_id,), one=True)
        if admin: user_data['name'] = admin['full_name']

    elif account['role'] == 'moderator':
        mod = query_db("SELECT * FROM Moderator WHERE account_id = %s", (account_id,), one=True)
        if mod: user_data['name'] = mod['full_name']

    return user_data

# Helper to get notifications
def get_notifications(account_id):
    return query_db("SELECT notif_id, message as msg, DATE_FORMAT(created_at, '%H:%i') as time, link FROM Notification WHERE user_id = %s ORDER BY created_at DESC", (account_id,))

# Helper to add notification
def add_notification(account_id, message, link=None):
    execute_db("INSERT INTO Notification (user_id, message, link) VALUES (%s, %s, %s)", (account_id, message, link))


# ==========================================
# UI STYLING 
# ==========================================

STYLES = """
<style>
    :root { 
        --bg: #f5f5f7; --card: #ffffff; --text: #0f1419; --sub: #536471; 
        --blue: #1d9bf0; --red: #f91880; --green: #00ba7c; --orange: #ff9f0a; 
        --shadow: 0 4px 20px rgba(0,0,0,0.08); --border: #eff3f4;
    }

    body { 
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; 
        background: var(--bg); 
        color: var(--text); 
        margin: 0; 
        padding-bottom: 50px; 
    }

    /* Update this inside your STYLES string */
    .profile-avatar { 
        width: 130px; 
        height: 130px; 
        background: white; 
        border: 4px solid white; 
        border-radius: 50%; 
        position: absolute; /* Keeps it attached to the banner */
        bottom: -65px; 
        left: 20px; 
        overflow: hidden; 
        display:flex; 
        align-items:center; 
        justify-content:center; 
        box-shadow: 0 4px 10px rgba(0,0,0,0.1); 
        z-index: 5;
    }

    a { color: var(--blue); text-decoration: none; font-weight: 500; transition: color 0.2s; }
    a:hover { text-decoration: underline; }
    
    .tweet-header img {
        border: 1px solid var(--border);
        background: #f0f0f0;
    }
    .rainbow-text {
            background: linear-gradient(to right, #ff0000, #ff7f00, #ffff00, #00ff00, #0000ff, #4b0082, #9400d3);
            background-size: 200% auto;
            color: #000; /* Fallback */
            background-clip: text;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            animation: rainbowMove 3s linear infinite;
        }

        @keyframes rainbowMove {
            to { background-position: 200% center; }
        }

    /* Nav */
    .nav { background: rgba(255,255,255,0.95); padding: 15px 40px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); position: sticky; top: 0; backdrop-filter: blur(10px); z-index: 100; }
    .nav-brand { font-weight: 800; font-size: 1.3rem; color: var(--blue); }
    .nav-links { display: flex; gap: 25px; }
    .nav-links a { color: var(--text); font-weight: 600; font-size: 1rem; }
    .nav-links a:hover { color: var(--blue); }
    .role-badge { background: #e5e5e5; padding: 4px 8px; border-radius: 6px; font-size: 0.7rem; text-transform: uppercase; margin-left: 8px; font-weight: 700; color: #555; vertical-align: middle; }

    /* Layout & Cards */
    .container { max-width: 900px; margin: 20px auto; padding: 0 20px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 25px; }
    .card { background: var(--card); border-radius: 16px; padding: 20px; box-shadow: var(--shadow); border: 1px solid var(--border); margin-bottom: 20px; }
    
    /* Profile Header */
    .profile-banner { height: 200px; background: linear-gradient(45deg, #a1c4fd, #c2e9fb); border-radius: 16px 16px 0 0; margin: 0; position: relative; }
    .profile-avatar { width: 130px; height: 130px; background: white; border: 4px solid white; border-radius: 50%; position: absolute; bottom: -65px; left: 20px; overflow: hidden; display:flex; align-items:center; justify-content:center; font-size:3rem; color:#ccc; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
    .profile-actions { display: flex; justify-content: flex-end; margin-top: 10px; height: 50px; }
    .profile-info { margin-top: 15px; }
    .profile-name { font-size: 1.5rem; font-weight: 800; margin: 0; }
    .profile-handle { color: var(--sub); font-size: 0.95rem; margin-bottom: 10px; }
    .profile-stats { display: flex; gap: 20px; margin-top: 15px; font-size: 0.95rem; }
    .stat-val { font-weight: 700; color: var(--text); }
    .stat-label { color: var(--sub); }
    
    /* Forum */
    .tweet-header { display: flex; gap: 10px; margin-bottom: 5px; }
    .tweet-avatar { width: 40px; height: 40px; background: #eee; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; color: #555; }
    .tweet-actions { display: flex; justify-content: space-between; margin-top: 15px; max-width: 300px; color: var(--sub); font-size: 0.9rem; }
    .tweet-action-btn { cursor: pointer; color: var(--sub); display: flex; align-items: center; gap: 5px; transition: color 0.2s; }
    .tweet-action-btn:hover.red { color: var(--red); }
    .tweet-action-btn:hover.green { color: var(--green); }
    .tweet-action-btn:hover.blue { color: var(--blue); }
    /* Elements */
    .btn { background: var(--text); color: white; border: none; padding: 10px 20px; border-radius: 999px; cursor: pointer; font-weight: 700; transition: 0.2s; font-size: 0.9rem; display: inline-block; text-decoration: none;}
    .btn:hover { background: #333; text-decoration: none; }
    .btn-blue { background: var(--blue); } .btn-blue:hover { background: #1a8cd8; }
    .btn-red { background: var(--red); }
    .btn-green { background: var(--green); }
    .btn-outline { background: transparent; border: 1px solid #cfd9de; color: var(--text); }
    .btn-outline:hover { background: #eff3f4; }
    .btn-sm { padding: 6px 12px; font-size: 0.8rem; }
    
    input, select, textarea { width: 100%; background: var(--bg); border: 1px solid transparent; padding: 12px; border-radius: 8px; margin-bottom: 10px; font-family: inherit; box-sizing: border-box; }
    input:focus, textarea:focus { outline: 2px solid var(--blue); background: white; }
    
    /* Friend List on Profile */
    .friend-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--border); }
    
    .alert-box { background: #e8f2ff; border-left: 4px solid var(--blue); color: var(--blue); padding: 15px; border-radius: 8px; margin-bottom: 25px; font-size: 0.95rem; }
    .badge { padding: 4px 10px; border-radius: 6px; font-size: 0.75rem; font-weight: 600; background: #e5e5e5; color: #555; }
    .notif-bubble { background: var(--red); color: white; border-radius: 10px; padding: 2px 6px; font-size: 0.7rem; vertical-align: top; margin-left: 2px; }
    
    table { width: 100%; border-collapse: separate; border-spacing: 0; margin-top: 10px; }
    th { text-align: left; padding: 12px; color: var(--sub); font-size: 0.8rem; text-transform: uppercase; font-weight: 600; border-bottom: 1px solid var(--border); }
    td { padding: 12px; border-bottom: 1px solid #f0f0f0; font-size: 0.9rem; }
    
    .chat-bubble { background: #e9e9eb; padding: 10px 16px; border-radius: 18px; margin-bottom: 8px; max-width: 70%; color: black; width: fit-content; }
    .chat-bubble.me { background: var(--blue); color: white; margin-left: auto; }
    
    /* Tinder Card */
    .tinder-container { perspective: 1000px; width: 100%; max-width: 400px; margin: 0 auto; }
    .tinder-card { background: white; border-radius: 20px; box-shadow: 0 10px 40px rgba(0,0,0,0.1); padding: 0; overflow: hidden; text-align: center; }
    .tinder-img { width: 100%; height: 200px; background: linear-gradient(to bottom right, #a1c4fd, #c2e9fb); display: flex; align-items: center; justify-content: center; font-size: 4rem; color: white; }
    .tinder-info { padding: 25px; }
    .tinder-actions { display: flex; justify-content: center; gap: 20px; padding-bottom: 25px; }
    .action-btn { width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; transition: transform 0.2s; cursor: pointer; border: 1px solid #eee; background: white; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }
    .action-btn:hover { transform: scale(1.1); }
    .btn-pass { color: var(--red); }
    .btn-like { color: var(--green); }

    /* TAB SYSTEM FOR PROFILE */
    .tab-item { padding:15px; font-weight:600; color:var(--sub); cursor:pointer; border-bottom: 4px solid transparent; transition: all 0.2s; }
    .tab-item:hover { background-color: rgba(0,0,0,0.03); }
    .tab-active { border-bottom:4px solid var(--blue); color:black; font-weight:700; }
</style>
"""

BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Digital Peer Support</title>
    {{ style|safe }}
</head>
<body>
    <div class="nav">
        <div class="nav-brand">PeerSupport <span class="role-badge">{{ role }}</span></div>
        <div class="nav-links">
            {% if role %}
                <a href="/dashboard">Dashboard 
                    {% if notif_count > 0 %}<span class="notif-bubble">{{ notif_count }}</span>{% endif %}
                </a>
                {% if role == 'student' %}
                    <a href="/forum">Forum</a>
                    <a href="/match">Match Up</a>
                    <a href="/chat">Chat</a>
                    <a href="/profile">Profile</a>
                {% endif %}
                <a href="/logout" style="color: var(--red);">Log Out</a>
            {% else %}
                <a href="/">Login</a>
            {% endif %}
        </div>
    </div>
    <div class="container">
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for msg in messages %}
                    <div class="alert-box">{{ msg }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        {% if notifications %}
        <div class="card" style="margin-bottom: 25px; border-left: 4px solid var(--orange);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <h3 style="margin:0; font-size:1.1rem;">🔔 Notifications</h3>
                <a href="/clear_notifs" style="font-size:0.85rem;">Clear All</a>
            </div>
            {% for n in notifications %}
                <div style="padding:10px 0; border-bottom:1px solid #f0f0f0;">
                    {{ n.msg }} <span style="color:var(--sub); font-size:0.8rem; margin-left:5px;">{{ n.time }}</span>
                </div>
            {% endfor %}
        </div>
        {% endif %}

        {content}
    </div>
</body>
</html>
"""

def render_page(content_html, **kwargs):
    role = session.get('role', '')
    uid = session.get('user_id')
    notifs = get_notifications(uid) if uid else []
    
    full_template = BASE_TEMPLATE.replace('{content}', content_html)
    return render_template_string(full_template, style=STYLES, role=role, notifications=notifs, notif_count=len(notifs), **kwargs)

# ==========================================
# AUTHENTICATION 
# ==========================================

@app.route('/')
def index():
    if 'user_id' in session: return redirect('/dashboard')
    html = """
    <div style="max-width:400px; margin:80px auto; text-align:center;">
        <div class="card">
            <h1>Welcome Back</h1>
            <p style="color:var(--sub); margin-bottom:30px;">Digital Peer Support System</p>
            <form method="POST" action="/login">
                <input type="text" name="username" placeholder="Username" required>
                <input type="password" name="password" placeholder="Password" required>
                <button class="btn" style="width:100%">Sign In</button>
            </form>
            <p style="margin-top:20px; font-size:0.9rem;">
                <a href="/forgot_password">Forgot Password?</a> | <a href="/signup">Create Account</a>
            </p>
            <div style="margin-top:30px; text-align:left; background:#f9f9f9; padding:15px; border-radius:10px; font-size:0.85rem; color:var(--sub);">
                <strong>Demo Accounts (Pass: 123)</strong><br>
                Student: <code>ashley</code>, <code>john</code><br>
                Admin: <code>admin</code><br>
                Moderator: <code>mod</code><br>
                Counselor: <code>counselor</code>
            </div>
        </div>
    </div>
    """
    return render_page(html)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        
        # --- PASSWORD VALIDATION LOGIC ---
        # 1. Check length
        if len(password) < 8:
            flash("Password must be at least 8 characters.")
            return redirect('/signup')
        # 2. Check for uppercase
        if not re.search(r"[A-Z]", password):
            flash("Password must contain at least one uppercase letter.")
            return redirect('/signup')
        # 3. Check for lowercase
        if not re.search(r"[a-z]", password):
            flash("Password must contain at least one lowercase letter.")
            return redirect('/signup')
        # 4. Check for digit (number)
        if not re.search(r"\d", password):
            flash("Password must contain at least one number.")
            return redirect('/signup')
        # 5. Check for symbol (special character)
        # [\W_] matches any non-alphanumeric character (symbols) or underscore
        if not re.search(r"[\W_]", password):
            flash("Password must contain at least one symbol (e.g., !@#$%).")
            return redirect('/signup')
        
        # 1. Create Account
        try:
            aid = execute_db("INSERT INTO Account (username, email, password, role) VALUES (%s, %s, %s, 'student')", (username, email, password))
            if aid:
                # 2. Create Student Profile (With 100 Points/Score default)
                execute_db("""
                    INSERT INTO Student (account_id, full_name, program, bio, score_percentage, points) 
                    VALUES (%s, %s, 'General', 'New here!', 100, 100)
                """, (aid, username))
                
                flash("Account created! ")
                return redirect('/')
            else:
                flash("Username or Email might already exist.")
        except Error as e:
            print(f"Signup Error: {e}")
            flash("Error creating account.")
            
    html = """
    <div style="max-width:400px; margin:80px auto; text-align:center;">
        <div class="card">
            <h1>Create Account</h1>
            <div style="background:#f0f8ff; padding:10px; font-size:0.8rem; text-align:left; border-radius:5px; margin-bottom:15px; color:#555;">
                <strong>Password Requirements:</strong><br>
                • At least 8 characters<br>
                • Uppercase & Lowercase letter<br>
                • A Number and a Symbol
            </div>
            <form method="POST">
                <input type="text" name="username" placeholder="Username" required>
                <input type="email" name="email" placeholder="MMU Student Email" pattern=".+@student\.mmu\.edu\.my" 
                    title="Please use your official MMU student email (xxxxxxxxxx@student.mmu.edu.my)" required>
                <input type="password" name="password" placeholder="Password" required>
                <button class="btn" style="width:100%">Sign Up</button>
            </form>
            <p style="margin-top:20px;"><a href="/">Back to Login</a></p>
        </div>
    </div>
    """
    return render_page(html)

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    
    user = query_db("SELECT * FROM Account WHERE username = %s AND password = %s", (username, password), one=True)
    
    if user:
        if not user['is_active']:
            session['temp_suspended_id'] = user['account_id']
            return redirect('/account_suspended')
            
        session['user_id'] = user['account_id']
        session['role'] = user['role']

        # --- NEW: LOG LOGIN SESSION TO DB ---
        execute_db("INSERT INTO LoginSession (account_id, login_time, is_active) VALUES (%s, NOW(), 1)", 
                   (user['account_id'],))
        # ------------------------------------

        return redirect('/dashboard')
    flash("Invalid credentials")
    return redirect('/')

@app.route('/account_suspended')
def account_suspended():
    aid = session.get('temp_suspended_id')
    if not aid: return redirect('/')
    
    # Fetch user details to show them why they are suspended
    user = query_db("""
        SELECT s.full_name, a.username 
        FROM Student s JOIN Account a ON s.account_id = a.account_id 
        WHERE a.account_id = %s
    """, (aid,), one=True)
    
    # Check if they already have a pending appeal
    student = query_db("SELECT student_id FROM Student WHERE account_id = %s", (aid,), one=True)
    existing_appeal = query_db("SELECT * FROM Appeal WHERE student_id = %s AND status='Pending'", (student['student_id'],), one=True)

    html = """
    <div style="max-width:500px; margin:80px auto;">
        <div class="card" style="border-top: 5px solid var(--red); text-align:center;">
            <h1 style="color:var(--red);">⛔ Account Suspended</h1>
            <p>Hi <strong>{{ user.full_name }}</strong>, your account has been suspended due to violations of our community guidelines.</p>
            
            {% if existing %}
                <div class="alert-box" style="margin-top:20px;">
                    <strong>Appeal Submitted</strong><br>
                    Your appeal is currently under review by an administrator. Please check back later.
                </div>
            {% else %}
                <p style="margin-top:20px;">If you believe this is a mistake, you may submit an appeal below.</p>
                <form action="/submit_external_appeal" method="POST" style="text-align:left; margin-top:20px;">
                    <label>Reason for Appeal / Explanation</label>
                    <textarea name="reason" rows="4" required placeholder="I apologize for my previous actions..." style="width:100%;"></textarea>
                    <button class="btn btn-red" style="width:100%;">Submit Appeal</button>
                </form>
            {% endif %}
            
            <a href="/logout" class="btn btn-outline" style="margin-top:20px; display:inline-block;">Back to Home</a>
        </div>
    </div>
    """
    return render_page(html, user=user, existing=existing_appeal)

@app.route('/submit_external_appeal', methods=['POST'])
def submit_external_appeal():
    aid = session.get('temp_suspended_id')
    if not aid: return redirect('/')
    
    student = query_db("SELECT student_id FROM Student WHERE account_id = %s", (aid,), one=True)
    reason = request.form['reason']
    
    if student:
        execute_db("INSERT INTO Appeal (student_id, reason) VALUES (%s, %s)", (student['student_id'], reason))
        flash("Appeal submitted successfully.")
    
    return redirect('/account_suspended')

@app.route('/logout')
def logout():
    # --- NEW: LOG LOGOUT SESSION TO DB ---
    uid = session.get('user_id')
    if uid:
        execute_db("INSERT INTO LogoutSession (account_id, logout_time) VALUES (%s, NOW())", (uid,))
    # -------------------------------------

    session.clear()
    return redirect('/')

# ==========================================
# FORGOT PASSWORD FLOW (Steps 1-8)
# ==========================================

# STEP 1 & 2: Click Forgot Password & Enter Email
@app.route('/forgot_password')
def forgot_password():
    html = """
    <div style="max-width:400px; margin:80px auto;">
        <div class="card">
            <h2>Reset Password</h2>
            <p style="color:var(--sub); margin-bottom:20px;">Enter your email to receive a One-Time Password (OTP).</p>
            <form action="/send_reset_otp" method="POST">
                <input type="email" name="email" placeholder="Registered Email" required>
                <button class="btn" style="width:100%">Send OTP</button>
            </form>
            <a href="/" style="display:block; margin-top:15px; text-align:center;">Back to Login</a>
        </div>
    </div>
    """
    return render_page(html)

@app.route('/send_reset_otp', methods=['POST'])
def send_reset_otp():
    email = request.form['email']
    
    # 1. Check if email exists in Account table
    account = query_db("SELECT * FROM Account WHERE email = %s", (email,), one=True)
    
    if not account:
        # Security: Don't reveal if email exists or not
        flash("Email not exist! ")
        return redirect('/forgot_password')

    # 2. Generate 4-digit OTP
    otp = str(random.randint(1000, 9999))
    
    # 3. Store in Session
    session['reset_email'] = email
    session['reset_otp'] = otp
    
    # 4. SEND ACTUAL EMAIL
    try:
        # Create the email message
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = email
        msg['Subject'] = "Password Reset - Digital Peer Support"

        body = f"""
        <html>
          <body>
            <h2>Peer Support System: Password Reset Request</h2>
            <p>Your One-Time Password (OTP) is:</p>
            <h1 style="color: #1d9bf0; letter-spacing: 5px;">{otp}</h1>
            <p>This code expires when you close your browser session.</p>
            <p>If you did not request this, please ignore this email.</p>
          </body>
        </html>
        """
        msg.attach(MIMEText(body, 'html'))

        # Connect to Server and Send
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls() # Secure the connection
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()

        flash(f"OTP sent to {email}. Please check your inbox.")
        return redirect('/enter_otp')

    except Exception as e:
        print(f"Email Error: {e}")
        flash("Failed to send email. Check server logs or internet connection.")
        return redirect('/forgot_password')
    
# STEP 5: Enter OTP Page
@app.route('/enter_otp')
def enter_otp():
    if 'reset_email' not in session:
        return redirect('/forgot_password')
        
    html = """
    <div style="max-width:400px; margin:80px auto;">
        <div class="card">
            <h2>Verify Identity</h2>
            <p>Please enter the 4-digit code sent to <strong>{{ email }}</strong></p>
            <form action="/verify_otp_action" method="POST">
                <input type="text" name="otp" placeholder="Enter 4-digit OTP" maxlength="4" style="letter-spacing: 5px; font-size: 1.2rem; text-align:center;" required>
                <button class="btn" style="width:100%">Verify Code</button>
            </form>
            <a href="/forgot_password" style="display:block; margin-top:15px; text-align:center; font-size:0.9rem;">Resend Code</a>
        </div>
    </div>
    """
    return render_page(html, email=session['reset_email'])

# STEP 6: Validate OTP
@app.route('/verify_otp_action', methods=['POST'])
def verify_otp_action():
    user_otp = request.form['otp']
    system_otp = session.get('reset_otp')
    
    if user_otp == system_otp:
        # OTP Matches. Mark session as verified
        session['otp_verified'] = True
        return redirect('/reset_new_password')
    else:
        flash("Invalid OTP. Please try again.")
        return redirect('/enter_otp')

# STEP 7: Set New Password Page
@app.route('/reset_new_password')
def reset_new_password():
    # Security check: User must have verified OTP to see this page
    if not session.get('otp_verified'):
        return redirect('/forgot_password')
        
    html = """
    <div style="max-width:400px; margin:80px auto;">
        <div class="card">
            <h2>Set New Password</h2>
            <div style="background:#f0f8ff; padding:10px; font-size:0.8rem; text-align:left; border-radius:5px; margin-bottom:15px; color:#555;">
                <strong>Requirements:</strong><br>
                • 8+ chars, Uppercase, Lowercase<br>
                • Number & Symbol
            </div>
            <form action="/perform_password_reset" method="POST">
                <input type="password" name="password" placeholder="New Password" required>
                <input type="password" name="confirm_password" placeholder="Confirm Password" required>
                <button class="btn btn-green" style="width:100%">Reset Password</button>
            </form>
        </div>
    </div>
    """
    return render_page(html)

# STEP 8: Update Database
@app.route('/perform_password_reset', methods=['POST'])
def perform_password_reset():
    if not session.get('otp_verified') or 'reset_email' not in session:
        return redirect('/')
        
    password = request.form['password']
    confirm = request.form['confirm_password']
    email = session['reset_email']
    
    # 1. Check Matching
    if password != confirm:
        flash("The password does not match.")
        return redirect('/reset_new_password')
        
    # 2. Check Complexity (Same logic as Signup)
    if len(password) < 8 or not re.search(r"[A-Z]", password) or \
       not re.search(r"[a-z]", password) or not re.search(r"\d", password) or \
       not re.search(r"[\W_]", password):
        flash("Password does not meet complexity requirements.")
        return redirect('/reset_new_password')
        
    # 3. Update Database
    execute_db("UPDATE Account SET password = %s WHERE email = %s", (password, email))
    
    # 4. Clear Session cleanup
    session.pop('reset_email', None)
    session.pop('reset_otp', None)
    session.pop('otp_verified', None)
    
    flash("🎉 Password reset successfully! Please login.")
    return redirect('/')

@app.route('/reset_verify', methods=['POST'])
def reset_verify():
    flash("OTP sent to email (Simulated: 1234).")
    return redirect('/')

@app.route('/clear_notifs')
def clear_notifs():
    execute_db("DELETE FROM Notification WHERE user_id = %s", (session['user_id'],))
    return redirect('/dashboard')

# ==========================================
# DASHBOARD CONTROLLER
# ==========================================

@app.route('/dashboard')
def dashboard():
    role = session.get('role')
    uid = session.get('user_id')
    
    if not uid: return redirect('/')
    
    user = get_user_by_id(uid)
    if not user:
        session.clear()
        return redirect('/')
    
    if role == 'student': return student_dashboard(user)
    if role == 'admin': return admin_dashboard()
    if role == 'moderator': return moderator_dashboard()
    if role == 'counselor': return counselor_dashboard()

# ==========================================
# STUDENT DASHBOARD & FEATURES
# ==========================================

def student_dashboard(user):
    user['is_restricted'] = user['points'] < CONFIG['restriction_threshold']
    
    # 1. Fetch last 7 mood logs for the graph
    mood_history = query_db("""
        SELECT mood_level, DATE_FORMAT(checkin_date, '%b %d') as day 
        FROM MoodCheckIn 
        WHERE student_id = %s 
        ORDER BY checkin_date DESC LIMIT 7
    """, (user['student_id'],))
    
    mood_history = mood_history[::-1]
    
    # Safely convert to JSON strings for JS
    labels = json.dumps([row['day'] for row in mood_history])
    values = json.dumps([row['mood_level'] for row in mood_history])

    anns = query_db("SELECT *, DATE_FORMAT(date, '%Y-%m-%d') as date_str FROM Announcement ORDER BY date DESC LIMIT 3")
    
    sessions = query_db("""
        SELECT ca.*, c.full_name as counselor_name, 
               DATE_FORMAT(ca.appointment_date, '%W, %d %M %Y at %H:%i') as date_pretty
        FROM CounselorAppointment ca
        JOIN Counselor c ON ca.counselor_id = c.counselor_id
        WHERE ca.student_id = %s 
          AND ca.status = 'Confirmed' 
          AND ca.appointment_date >= NOW()
        ORDER BY ca.appointment_date ASC
    """, (user['student_id'],))

    friend_requests = query_db("""
        SELECT f.student_id_1 as requester_id, s.full_name, s.program, s.account_id
        FROM Friendship f
        JOIN Student s ON f.student_id_1 = s.student_id
        WHERE f.student_id_2 = %s AND f.status = 'Pending'
    """, (user['student_id'],))

    # Using an f-string requires double braces for literal JS braces
    content = f"""
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

        <div style="display:flex; justify-content:space-between; align-items:start; margin-bottom:20px;">
            <div>
                <h1 style="margin-bottom:5px;">Hi, {{{{ user.name }}}} 👋</h1>
                <span style="color:var(--sub);">{{{{ user.program }}}} Student | <strong>{{{{ user.points }}}} Points</strong></span>
            </div>
            <div style="text-align:right;">
                 <span class="badge" style="background:var(--blue); color:white; font-size:1rem;">Wellness Score: {{{{ user.score }}}}%</span>
            </div>
        </div>

        <div class="grid" style="grid-template-columns: 2fr 1fr;">
            <div class="card">
                <h3>Mood Trend (Last 7 Logs)</h3>
                <canvas id="moodChart" height="150"></canvas>
            </div>

            <div class="card">
                <h3>Log Today's Mood</h3>
                <p style="color:var(--sub); font-size:0.9rem;">How are you feeling?</p>
                <form action="/mood_checkin" method="POST">
                    <div style="display:flex; justify-content:space-between; margin-bottom:15px; font-size:1.5rem;">
                        <label style="cursor:pointer"><input type="radio" name="level" value="1"> 😫</label>
                        <label style="cursor:pointer"><input type="radio" name="level" value="2"> 😔</label>
                        <label style="cursor:pointer"><input type="radio" name="level" value="3" checked> 😐</label>
                        <label style="cursor:pointer"><input type="radio" name="level" value="4"> 🙂</label>
                        <label style="cursor:pointer"><input type="radio" name="level" value="5"> 😄</label>
                    </div>
                    <button class="btn btn-blue" style="width:100%">Submit Entry</button>
                </form>
            </div>
        </div>

        <script>
            const ctx = document.getElementById('moodChart').getContext('2d');
            new Chart(ctx, {{
                type: 'line',
                data: {{
                    labels: {labels},
                    datasets: [{{
                        label: 'Mood Level',
                        data: {values},
                        borderColor: '#1d9bf0',
                        backgroundColor: 'rgba(29, 155, 240, 0.1)',
                        fill: true,
                        tension: 0.4,
                        borderWidth: 3,
                        pointBackgroundColor: '#1d9bf0'
                    }}]
                }},
                options: {{
                    scales: {{
                        y: {{ 
                            min: 1, max: 5,
                            ticks: {{ stepSize: 1, callback: function(value) {{
                                const emoji = ["", "😫", "😔", "😐", "🙂", "😄"];
                                return emoji[value];
                            }} }}
                        }}
                    }},
                    plugins: {{ legend: {{ display: false }} }}
                }}
            }});
        </script>

        {{% if user.is_restricted %}}
        <div class="alert-box" style="border-color:var(--red); color:var(--red); background:#fff5f5;">
            <strong>⚠️ Account Restricted</strong><br>
            Your Safety Score is {{ user.score }}% (Below 60%). You cannot post or comment.
            <form action="/submit_appeal" method="POST" style="margin-top:10px;">
                <input type="text" name="reason" placeholder="Reason for appeal..." required style="margin-bottom:5px;">
                <button class="btn btn-red btn-sm">Submit Appeal</button>
            </form>
        </div>
        {{% endif %}}

        <div class="grid">
            {{% if friend_requests %}}
            <div class="card" style="border-left: 4px solid var(--orange);">
                <h3>💌 Friend Requests</h3>
                {{% for req in friend_requests %}}
                    <div style="display:flex; justify-content:space-between; align-items:center; padding:10px 0; border-bottom:1px solid #f0f0f0;">
                        <div>
                            <strong>{{{{ req.full_name }}}}</strong><br>
                            <span style="font-size:0.8rem; color:var(--sub);">{{{{ req.program }}}}</span>
                        </div>
                        <div style="display:flex; gap:5px;">
                            <a href="/accept_friend/{{{{ req.account_id }}}}" class="btn btn-green btn-sm">Accept</a>
                            <a href="/decline_friend/{{{{ req.account_id }}}}" class="btn btn-red btn-sm">Decline</a>
                        </div>
                    </div>
                {{% endfor %}}
            </div>
            {{% endif %}}

            <div class="card" style="border-left: 4px solid var(--blue);">
                <h3>📅 Upcoming Sessions</h3>
                {{% if sessions %}}
                    {{% for s in sessions %}}
                        <div style="margin-bottom:15px; padding-bottom:10px; border-bottom:1px solid #f0f0f0;">
                            <strong>With {{{{ s.counselor_name }}}}</strong><br>
                            <span style="font-size:0.9rem; color:var(--text);">{{{{ s.date_pretty }}}}</span><br>
                            <span style="font-size:0.8rem; color:var(--sub);">Topic: {{{{ s.reason }}}}</span>
                        </div>
                    {{% endfor %}}
                {{% else %}}
                    <p style="color:var(--sub); font-size:0.9rem;">No upcoming sessions scheduled.</p>
                    <a href="/book_appointment" style="font-size:0.85rem; font-weight:bold;">Book Now &rarr;</a>
                {{% endif %}}
            </div>

            <div class="card" style="border-left: 4px solid var(--green);">
                <h3>📢 Announcements</h3>
                {{% for a in announcements %}}
                    <div style="margin-bottom:15px; padding-bottom:10px; border-bottom:1px solid #f0f0f0;">
                        <strong>{{{{ a.title }}}}</strong> <span style="font-size:0.8rem; color:var(--sub); float:right;">{{{{ a.date_str }}}}</span><br>
                        <span style="font-size:0.9rem; color:var(--text);">{{{{ a.content }}}}</span>
                    </div>
                {{% endfor %}}
            </div>

            <div class="card">
                <h3>Quick Actions</h3>
                <a href="/match" class="btn btn-outline" style="width:100%; margin-bottom:10px; display:block; text-align:center;">🔥 Find Friends</a>
                <a href="/book_appointment" class="btn btn-outline" style="width:100%; display:block; text-align:center;">📅 Book Counselor</a>
            </div>
        </div>
    """
    return render_page(content, user=user, announcements=anns, sessions=sessions, friend_requests=friend_requests)

@app.route('/mood_checkin', methods=['POST'])
def mood_checkin():
    user = get_user_by_id(session['user_id'])

    # 1. Check if already checked in today
    already_checked_in = query_db("""
        SELECT checkin_id FROM MoodCheckIn 
        WHERE student_id = %s AND DATE(checkin_date) = CURDATE()
    """, (user['student_id'],), one=True)

    if already_checked_in:
        flash("You have already checked in today. Please try again tomorrow.")
        return redirect('/dashboard')
   
    lvl = int(request.form.get('level', 3))
    severity = 'Critical' if lvl <= 2 else 'Low'
    
    # 2. Insert the new Mood Entry
    execute_db("INSERT INTO MoodCheckIn (student_id, mood_level, severity_level, note) VALUES (%s, %s, %s, 'User check-in')", 
               (user['student_id'], lvl, severity))
    
    # 3. UPDATE GAMIFICATION POINTS (Using the Helper)
    # This adds to 'points' with daily limit check
    update_student_score(user['student_id'], CONFIG['points_checkin'], "Mood Check-in")
    
    # 4. CALCULATE WELLNESS BATTERY (For 'score_percentage')
    history = query_db("SELECT mood_level FROM MoodCheckIn WHERE student_id = %s ORDER BY checkin_date ASC", (user['student_id'],))
    
    wellness_battery = 100 # Starts at 100%
    
    if history:
        for log in history:
            m = log['mood_level']
            if m == 1: wellness_battery -= 20
            elif m == 2: wellness_battery -= 10
            elif m == 3: wellness_battery -= 5
            elif m == 4: wellness_battery += 5
            elif m == 5: wellness_battery += 15
            
            # Clamp between 0 and 100
            if wellness_battery > 100: wellness_battery = 100
            if wellness_battery < 0: wellness_battery = 0

    # 5. UPDATE SCORE_PERCENTAGE (This column is now EXCLUSIVELY for Wellness)
    execute_db("UPDATE Student SET score_percentage = %s WHERE student_id = %s", (wellness_battery, user['student_id']))

    msg = f"Mood logged! Your Mental Wellness Battery is at {wellness_battery}%."
    if wellness_battery < 30:
        msg += " (Alert: Your battery is critical. Consider booking a session.)"
        
    flash(msg)
    return redirect('/dashboard')

@app.route('/submit_appeal', methods=['POST'])
def submit_appeal():
    user = get_user_by_id(session['user_id'])
    execute_db("INSERT INTO Appeal (student_id, reason) VALUES (%s, %s)", (user['student_id'], request.form['reason']))
    flash("Your appeal submitted to Admin.")
    return redirect('/dashboard')

# --- FORUM FEATURES ---
@app.route('/forum', methods=['GET', 'POST'])
def forum():
    user = get_user_by_id(session.get('user_id'))
    if not user: return redirect('/logout')

    if request.method == 'POST':
        #  handle the forum posting
        if user['points'] < 60:
            flash("Restricted users cannot post.")
            return redirect('/forum')
        
        content = request.form['content']
        anon = 1 if 'anon' in request.form else 0
        
        # --- CLOUDINARY UPLOAD LOGIC ---
        files = request.files.getlist('file')

        if len(files) > 5:
            flash("Exceed 5 files! Please select 5 or fewer files only.")
            return redirect('/forum')
        
        file_urls = []
        
        for file in files[:5]:
            if file and file.filename != '':
                # 1. Check extension BEFORE uploading
                if allowed_file(file.filename):
                    try:
                        upload_result = cloudinary.uploader.upload(
                            file, 
                            resource_type="auto", 
                            public_id=file.filename.rsplit('.', 1)[0] # Clean filename
                        )
                        file_urls.append(upload_result['secure_url'])
                    except Exception as e:
                        print(f"Cloudinary Error: {e}")
                        flash(f"Cloudinary upload failed for {file.filename}.")
                else:
                    flash(f"File type not allowed: {file.filename}")

        # Join URLs with a comma to store in DB
        image_url_str = ",".join(file_urls)
        
        execute_db("INSERT INTO Post (student_id, content, image_url, is_anonymous) VALUES (%s, %s, %s, %s)", 
                   (user['student_id'], content, image_url_str, anon))
        update_student_score(user['student_id'], CONFIG['points_post'], "Created Post")
        flash("Posted!")
        return redirect('/forum')
    
    # --- FETCH POSTS ---
    sql = """
        SELECT p.*, s.full_name, s.avatar_url, s.points, a.username, 
        DATE_FORMAT(p.created_at, '%Y-%m-%d %H:%i') as date_str,
        (SELECT COUNT(*) FROM Comment c WHERE c.post_id = p.post_id) as comment_count
        FROM Post p
        JOIN Student s ON p.student_id = s.student_id
        JOIN Account a ON s.account_id = a.account_id
        ORDER BY p.created_at DESC
    """
    raw_posts = query_db(sql)
    
    # Safety Check: If DB fails, prevent crash
    if raw_posts is None:
        raw_posts = []

    posts_ui = []
    
    # Process Posts
    for p in raw_posts:
        author = "Anonymous" if p['is_anonymous'] else p['full_name']

        file_list = []
        if p.get('image_url'):
            file_list = [f.strip() for f in p['image_url'].split(',') if f.strip()]
        
        posts_ui.append({
            'id': p['post_id'], 
            'content': p['content'], 
            'author': author, 
            'points': p['points'], 
            'files': file_list,
            'likes': p['likes'], 
            'date': p['date_str'],
            'comments_count': p['comment_count'],
            'avatar': p['avatar_url'] if not p['is_anonymous'] else 'https://api.dicebear.com/7.x/bottts/svg?seed=Anon',
        })

    content = """
        <div style="max-width:600px; margin:0 auto;">
            <div class="card">
                <form method="POST" enctype="multipart/form-data"> 
                    <div style="display:flex; gap:15px;">
                        <img src="{{ user.avatar }}" style="width:45px; height:45px; border-radius:50%; object-fit:cover;">
                        <div style="flex:1;">
                            <textarea name="content" placeholder="What's on your mind?" rows="2" style="border:none; background:transparent; font-size:1.1rem; resize:none;" required></textarea>
                            
                            <div style="margin: 10px 0;">
                                <label style="font-size: 0.85rem; color: var(--blue); cursor: pointer; display: flex; align-items: center; gap: 5px;">
                                    <span style="font-size: 1.2rem;">📎</span> 
                                    <span id="file-count-label">Add Photos/Files (Max 5)</span>
                                    <input type="file" name="file" multiple style="display: none;" 
                                        onchange="document.getElementById('file-count-label').innerText = this.files.length + ' files selected'">
                                </label>
                            </div>

                            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px; border-top:1px solid #eee; padding-top:10px;">
                                <label style="color:var(--blue); font-size:0.9rem; cursor:pointer;"><input type="checkbox" name="anon"> Post Anonymous</label>
                                <button class="btn btn-blue">Post</button>
                            </div>
                        </div>
                    </div>
                </form>
            </div>

            <h3 style="margin-top:30px; margin-bottom:15px;">Recent Feed</h3>

            {% for post in posts %}
            <div class="card" style="padding-bottom:10px;">
                <div class="tweet-header">
                    <img src="{{ post.avatar }}" style="width:48px; height:48px; border-radius:50%; object-fit:cover; margin-right:10px;">
                    <div>
                        <strong class="{% if post.points >= 95 %}rainbow-text{% endif %}">{{ post.author }}</strong> 
                        <span style="color:var(--sub);">@{{ post.author.lower().replace(' ','') }} · {{ post.date }}</span>
                    </div>
                </div>
                <div style="padding-left: 58px;">
                    <p style="margin:5px 0 15px 0; font-size:1rem; line-height:1.5;">{{ post.content }}</p>

                    {% if post.files %}
                    <div style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 15px;">
                        {% for url in post.files %}
                            {# Use a more robust check: lower() and checking if the substring exists #}
                            {% if '.jpg' in url.lower() or '.jpeg' in url.lower() or '.png' in url.lower() or '.gif' in url.lower() %}
                                <img src="{{ url }}" style="max-width: 100%; border-radius: 12px; border: 1px solid var(--border); max-height: 300px;" onerror="this.style.display='none'">
                            {% elif '.mp4' in url.lower() or '.mov' in url.lower() %}
                                <video controls style="max-width: 100%; border-radius: 12px; max-height: 300px;">
                                    <source src="{{ url }}" type="video/mp4">
                                </video>
                            {% else %}
                                <a href="{{ url }}" target="_blank" class="btn btn-sm btn-outline">View Attachment</a>
                            {% endif %}
                        {% endfor %}
                    </div>
                    {% endif %}

                    <div class="tweet-actions">
                        <a href="/post_detail/{{ post.id }}" class="tweet-action-btn blue">💬 {{ post.comments_count }}</a>
                        <a href="/like_post/{{ post.id }}" class="tweet-action-btn red">♥ {{ post.likes }}</a>
                        <button onclick="openReportModal('post', {{ post.id }})" class="tweet-action-btn" style="background:none;border:none;cursor:pointer;">⚠</button>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        
        <div id="report-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:999;">
            <div class="card" style="max-width:400px; margin:100px auto;">
                <h3>Report Content</h3>
                <form action="/submit_report" method="POST">
                    <input type="hidden" name="type" id="rep_type"> 
                    <input type="hidden" name="id" id="rep_id">     
                    <label>Reason:</label>
                    <select name="reason" required>
                        <option value="Harassment">Harassment</option>
                        <option value="Spam">Spam</option>
                        <option value="Inappropriate">Inappropriate</option>
                    </select>
                    <div style="margin-top:15px; text-align:right;">
                        <button type="button" onclick="document.getElementById('report-modal').style.display='none'" class="btn btn-outline">Cancel</button>
                        <button class="btn btn-red">Submit</button>
                    </div>
                </form>
            </div>
        </div>

        <script>
        function openReportModal(type, id) {
            document.getElementById('report-modal').style.display = 'block';
            document.getElementById('rep_type').value = type;
            document.getElementById('rep_id').value = id;
        }
        </script>
    """
    return render_page(content, posts=posts_ui, user=user)

@app.route('/post_detail/<int:pid>', methods=['GET', 'POST'])
def post_detail(pid):
    # Fetch post
    p = query_db("""
        SELECT p.*, s.full_name, a.username 
        FROM Post p 
        JOIN Student s ON p.student_id = s.student_id 
        JOIN Account a ON s.account_id = a.account_id 
        WHERE p.post_id = %s
    """, (pid,), one=True)

    if not p: return redirect('/forum')
    
    p['files'] = []
    if p.get('image_url'):
        p['files'] = [f.strip() for f in p['image_url'].split(',') if f.strip()]
    
    #anon still get points 
    if request.method == 'POST':
        user = get_user_by_id(session['user_id'])
        content = request.form['content']
        anon = 1 if 'anon' in request.form else 0 #check tickbox from HTML
        execute_db("INSERT INTO Comment (post_id, student_id, content, is_anonymous) VALUES (%s, %s, %s, %s)", 
                   (pid, user['student_id'], content, anon))
        update_student_score(user['student_id'], CONFIG['points_comment'], "Commented")
        return redirect(f'/post_detail/{pid}')

    # Fetch comments (Query includes the Like Count as 'db_likes')
    comments = query_db("""
        SELECT 
            c.*, 
            s.full_name,
            (SELECT COUNT(*) FROM `Like` WHERE comment_id = c.comment_id) as db_likes
        FROM Comment c 
        JOIN Student s ON c.student_id = s.student_id 
        WHERE c.post_id = %s 
        ORDER BY c.created_at ASC
    """, (pid,))
    
    # pass 'comments' directly to the template so it has all the IDs and Names 

    content = """
        <a href="/forum">Back to Forum</a>
        <h3>Comments</h3>
        <div class="card">
            <form method="POST">
                <textarea name="content" placeholder="Write a comment..." required></textarea>
                <div style="margin-top:10px;">
                    <label><input type="checkbox" name="anon"> Anonymous</label>
                    <button class="btn btn-sm" style="float:right;">Reply</button>
                </div>
            </form>
        </div>
        
        {% for c in comments %}
            <div class="card" style="margin-top:15px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <strong>{{ c.full_name if not c.is_anonymous else 'Anonymous' }}</strong>
                    
                    <div style="font-size:0.85rem; color:var(--sub);">
                        <a href="/like_comment/{{ c.comment_id }}" style="text-decoration:none; margin-right:15px; color:var(--red);">
                            ♥ {{ c.db_likes }}
                        </a>
                        
                        <a href="#" onclick="openReportModal('comment', {{ c.comment_id }})" style="text-decoration:none; color:var(--sub);">
                            ⚠ Report
                        </a>
                    </div>
                </div>
                <p style="margin-top:5px;">{{ c.content }}</p>
            </div>
        {% endfor %}

        <div id="report-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:999;">
            <div class="card" style="max-width:400px; margin:100px auto;">
                <h3>Report Content</h3>
                <form action="/submit_report" method="POST">
                    <input type="hidden" name="type" id="rep_type"> 
                    <input type="hidden" name="id" id="rep_id">     
                    <label>Reason:</label>
                    <select name="reason" required>
                        <option value="Harassment">Harassment</option>
                        <option value="Spam">Spam</option>
                        <option value="Inappropriate">Inappropriate</option>
                    </select>
                    
                    <div style="margin-top:15px; text-align:right;">
                        <button type="button" onclick="document.getElementById('report-modal').style.display='none'" class="btn btn-outline">Cancel</button>
                        <button class="btn btn-red">Submit</button>
                    </div>
                </form>
            </div>
        </div>

        <script>
        function openReportModal(type, id) {
            document.getElementById('report-modal').style.display = 'block';
            document.getElementById('rep_type').value = type;
            document.getElementById('rep_id').value = id;
        }
        </script>
    """
    # PASS RAW COMMENTS HERE
    return render_page(content, comments=comments)

# --- LIKE POST (Using the Like Table) ---
@app.route('/like_post/<int:pid>')
def like_post(pid):
    user_id = session.get('user_id')
    if not user_id: return redirect('/login')

    # Get student_id (needed for the Like table)
    student = query_db("SELECT student_id FROM Student WHERE account_id = %s", (user_id,), one=True)
    if not student: return redirect('/logout')

    # Check if already liked
    existing = query_db("SELECT * FROM `Like` WHERE student_id = %s AND post_id = %s", 
                        (student['student_id'], pid), one=True)
    
    if not existing:
        # Insert into Like table
        execute_db("INSERT INTO `Like` (student_id, post_id, liked_at) VALUES (%s, %s, NOW())", 
                   (student['student_id'], pid))
        
        # Update the counter on Post table 
        execute_db("UPDATE Post SET likes = likes + 1 WHERE post_id = %s", (pid,))

        # --- NEW: GIVE POINTS FOR LIKING ---
        update_student_score(student['student_id'], CONFIG['points_like'], "Liked a Post")
    else:
        # Toggle to Unlike 
        execute_db("DELETE FROM `Like` WHERE like_id = %s", (existing['like_id'],))
        execute_db("UPDATE Post SET likes = likes - 1 WHERE post_id = %s", (pid,))

    return redirect(request.referrer)

# --- LIKE COMMENT (Using the Like Table) ---
@app.route('/like_comment/<int:cid>')
def like_comment(cid):
    user_id = session.get('user_id')
    if not user_id: return redirect('/login')

    # Get student ID
    student = query_db("SELECT student_id FROM Student WHERE account_id = %s", (user_id,), one=True)
    if not student: return redirect('/logout')
    sid = student['student_id']

    # Check if already liked in the 'Like' table
    existing = query_db("SELECT * FROM `Like` WHERE student_id = %s AND comment_id = %s", (sid, cid), one=True)
    
    if existing:
        # Unlike (Toggle Off)
        execute_db("DELETE FROM `Like` WHERE like_id = %s", (existing['like_id'],))
    else:
        # Like (Toggle On) - Note: post_id is NULL here because it's a comment
        execute_db("INSERT INTO `Like` (student_id, comment_id, liked_at) VALUES (%s, %s, NOW())", (sid, cid))
    
    return redirect(request.referrer)

# --- REPORT SUBMISSION ---
@app.route('/submit_report', methods=['POST'])
def submit_report():
    target_type = request.form['type'] # 'post' or 'comment'
    target_id = request.form['id']
    reason = request.form['reason']
    
    execute_db("INSERT INTO Report (reporter_id, target_type, target_id, reason) VALUES (%s, %s, %s, %s)",
               (session['user_id'], target_type, target_id, reason))
    
    flash("Report submitted.")
    return redirect(request.referrer)

# --- MATCH UP ---
@app.route('/match')
def match_up():
    user = get_user_by_id(session.get('user_id'))
    if not user: return redirect('/logout')

    skipped_ids = session.get('skipped_matches', [])
    
    # 1. NEW: Get IDs of everyone I already have a connection with (Pending OR Accepted)
    # This prevents users from reappearing if you already sent a request
    existing_connections = query_db("""
        SELECT student_id_1, student_id_2 
        FROM Friendship 
        WHERE student_id_1 = %s OR student_id_2 = %s
    """, (user['student_id'], user['student_id']))
    
    # Flatten into a set of Student IDs to exclude
    exclude_ids = set()
    for row in existing_connections:
        exclude_ids.add(row['student_id_1'])
        exclude_ids.add(row['student_id_2'])
    
    # 2. Get all students except me
    all_students = query_db("SELECT * FROM Student WHERE student_id != %s", (user['student_id'],))
    
    candidates = []
    my_interests = set(user['interests'])
    
    for s in all_students:
        # Filter: Exclude anyone in the existing connections list (Friends or Pending)
        if s['student_id'] in exclude_ids: continue
        
        # Filter: Exclude session skips
        if s['account_id'] in skipped_ids: continue
        
        their_interests = set(s['interests'].split(',')) if s['interests'] else set()
        common = my_interests & their_interests
        
        # Show if common interests exist OR if I have no interests yet
        if common or not my_interests:
            s['interests_list'] = list(their_interests)
            candidates.append(s)
    
    match = candidates[0] if candidates else None
    
    # ... (Keep the rest of your content/HTML exactly the same) ...
    content = """
        <div class="tinder-container">
            <h1 style="text-align:center; margin-bottom:30px;">Find Peers</h1>
            {% if match %}
            <div class="tinder-card">
                <div class="tinder-img">👤</div>
                <div class="tinder-info">
                    <h2>{{ match.full_name }}</h2>
                    <p style="color:var(--sub);">{{ match.program }}</p>
                    <p style="font-style:italic; margin:15px 0;">"{{ match.bio }}"</p>
                    <div style="margin-bottom:10px;">
                        {% for i in match.interests_list %}
                            <span class="badge">{{ i }}</span>
                        {% endfor %}
                    </div>
                </div>
                <div class="tinder-actions">
                    <a href="/match_skip/{{ match.account_id }}" class="action-btn btn-pass">✕</a>
                    <a href="/match_connect/{{ match.account_id }}" class="action-btn btn-like">♥</a>
                </div>
            </div>
            {% else %}
            <div class="card" style="text-align:center;">
                <h3>No more matches!</h3>
                <p>Try refreshing later or update your interests.</p>
                <a href="/profile" class="btn">Update Profile</a>
                <br><br>
                <a href="/match_reset" class="btn btn-outline btn-sm">Reset Skips</a>
            </div>
            {% endif %}
        </div>
    """
    return render_page(content, match=match)

@app.route('/match_connect/<int:tid>')
def match_connect(tid): # tid is target account_id
    user = get_user_by_id(session['user_id'])
    target_user = get_user_by_id(tid)
    
    add_notification(tid, f"{user['name']} wants to connect!", f"/accept_friend/{user['id']}")
    
    # Insert Pending Friendship
    execute_db("INSERT INTO Friendship (student_id_1, student_id_2, status) VALUES (%s, %s, 'Pending')", 
               (user['student_id'], target_user['student_id']))
    
    flash("Friend request sent!")
    skipped = session.get('skipped_matches', [])
    skipped.append(tid)
    session['skipped_matches'] = skipped
    return redirect('/match')

@app.route('/match_skip/<int:tid>')
def match_skip(tid):
    skipped = session.get('skipped_matches', [])
    skipped.append(tid)
    session['skipped_matches'] = skipped
    return redirect('/match')

@app.route('/match_reset')
def match_reset():
    session['skipped_matches'] = []
    return redirect('/match')

@app.route('/accept_friend/<int:rid>') # rid is requester account_id
def accept_friend(rid):
    me = get_user_by_id(session['user_id'])
    requester = get_user_by_id(rid)
    
    # Update Status to Accepted
    execute_db("""
        UPDATE Friendship 
        SET status = 'Accepted' 
        WHERE student_id_1 = %s AND student_id_2 = %s
    """, (requester['student_id'], me['student_id']))
    
    add_notification(rid, f"{me['name']} accepted your request.")
    flash("Friend added!")
    return redirect('/profile')

@app.route('/decline_friend/<int:rid>') # rid is requester account_id
def decline_friend(rid):
    me = get_user_by_id(session['user_id'])
    requester = get_user_by_id(rid)

    # 1. Update Status to 'Declined' (or you could use DELETE FROM to remove it entirely)
    execute_db("""
        UPDATE Friendship 
        SET status = 'Declined' 
        WHERE student_id_1 = %s AND student_id_2 = %s
    """, (requester['student_id'], me['student_id']))

    # 2. Optional: Notify the requester (Often skipped to be polite, but added per your requirements)
    # add_notification(rid, f"{me['name']} declined your friend request.") 

    flash("Friend request declined.")
    return redirect('/dashboard')

@app.route('/chat', defaults={'friend_id': None})
@app.route('/chat/<int:friend_id>', methods=['GET', 'POST'])
def chat(friend_id):
    # friend_id here is Account ID
    uid = session.get('user_id')
    user = get_user_by_id(uid)
    
    friends = []
    for fid in user['friends']:
        f = get_user_by_id(fid)
        if f: friends.append(f)
    
    if request.method == 'POST':
        msg = request.form['msg']
        execute_db("INSERT INTO PrivateChat (sender_id, receiver_id, message) VALUES (%s, %s, %s)", (uid, friend_id, msg))
        return redirect(f'/chat/{friend_id}')
    
    history = []
    if friend_id:
        history = query_db("""
            SELECT *, CASE WHEN sender_id = %s THEN 1 ELSE 0 END as is_me 
            FROM PrivateChat 
            WHERE (sender_id = %s AND receiver_id = %s) OR (sender_id = %s AND receiver_id = %s)
            ORDER BY sent_at ASC
        """, (uid, uid, friend_id, friend_id, uid))
    
    content = """
        <div style="display:grid; grid-template-columns: 1fr 2fr; gap:25px; height:600px;">
            <div class="card" style="overflow-y:auto; padding:0;">
                <div style="padding:20px; border-bottom:1px solid #f0f0f0;"><h3>Conversations</h3></div>
                {% for f in friends %}
                    <a href="/chat/{{ f.id }}" style="display:block; padding:15px 20px; border-bottom:1px solid #f0f0f0; color:var(--text);">
                        <strong>{{ f.name }}</strong>
                    </a>
                {% endfor %}
            </div>
            <div class="card" style="display:flex; flex-direction:column;">
                {% if friend_id %}
                    <div style="flex:1; overflow-y:auto; padding:10px;">
                        {% for msg in history %}
                            <div class="chat-bubble {% if msg.is_me %}me{% endif %}">{{ msg.message }}</div>
                        {% endfor %}
                    </div>
                    <form method="POST" style="margin-top:15px; display:flex; gap:10px;">
                        <input type="text" name="msg" required style="margin:0;" placeholder="Type a message...">
                        <button class="btn">Send</button>
                    </form>
                {% else %}<p style="margin:auto; color:var(--sub);">Select a friend to start chatting</p>{% endif %}
            </div>
        </div>
    """
    return render_page(content, friends=friends, friend_id=friend_id, history=history)

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    user = get_user_by_id(session.get('user_id'))

    AVATAR_OPTIONS = [
        "https://api.dicebear.com/7.x/avataaars/svg?seed=Felix",
        "https://api.dicebear.com/7.x/avataaars/svg?seed=Aneka",
        "https://api.dicebear.com/7.x/avataaars/svg?seed=Buddy",
        "https://api.dicebear.com/7.x/avataaars/svg?seed=Max",
        "https://api.dicebear.com/7.x/avataaars/svg?seed=Luna",
        "https://api.dicebear.com/7.x/avataaars/svg?seed=Zoe"
    ]
    
    # 1. HANDLE PROFILE UPDATES
    if request.method == 'POST':
        bio = request.form['bio']
        prog = request.form['program']
        interests = request.form['interests'] 
        
        # Update SQL
        avatar_url = request.form.get('avatar_url')
        execute_db("UPDATE Student SET bio = %s, program = %s, interests = %s, avatar_url = %s WHERE student_id = %s", 
                   (bio, prog, interests, avatar_url, user['student_id']))
        
        flash("Profile updated successfully.")
        return redirect('/profile')

    # 2. GET USER DATA
    my_posts_raw = query_db("""
        SELECT p.*, (SELECT COUNT(*) FROM Comment c WHERE c.post_id = p.post_id) as c_count 
        FROM Post p WHERE p.student_id = %s ORDER BY created_at DESC
    """, (user['student_id'],))
    
    my_posts = []
    for p in my_posts_raw:
        my_posts.append({
            'id': p['post_id'], 
            'content': p['content'], 
            'likes': p['likes'], 
            'is_retweet': p['is_retweet'],
            'comments_count': p['c_count'], 
            'date': p['created_at'].strftime("%Y-%m-%d")
        })

    friends_list = []
    for fid in user['friends']:
        friends_list.append(get_user_by_id(fid))

    # 3. RENDER PAGE (FIXED BRACKETS)
    content = """
        <div style="max-width:600px; margin:0 auto;">
            <div class="card" style="padding:0; overflow:visible;">
                <div class="profile-banner"></div>
                <div style="padding: 0 20px 20px 20px;">
                    <div class="profile-actions">
                        <button onclick="document.getElementById('edit-modal').style.display='block'" class="btn btn-outline">Edit Profile</button>
                    </div>
                    
                    <div class="profile-avatar">
                        <img src="{{ user.avatar }}" style="width:100%; height:100%; object-fit:cover; border-radius:50%;">
                    </div>
                    
                    <div class="profile-info">
                        <h1 class="profile-name {% if user.points >= 95 %}rainbow-text{% endif %}">
                            {{ user.name }} <span style="font-size:1rem; color:var(--blue);">✓</span>
                        </h1>
                        <div class="profile-handle">@{{ user.username }} • {{ user.program }}</div>
                        <p style="margin:10px 0;">{{ user.bio }}</p>
                        
                        <div class="profile-stats">
                            <span><span class="stat-val">{{ friends_list|length }}</span> <span class="stat-label">Friends</span></span>
                            <span><span class="stat-val">{{ my_posts|length }}</span> <span class="stat-label">Posts</span></span>
                            <span><span class="stat-val">{{ user.points }}</span> <span class="stat-label">Points</span></span>
                        </div>
                    </div>
                </div>
            </div>

            <div style="display:flex; border-bottom:1px solid var(--border); margin-bottom:20px;">
                <div class="tab-item tab-active" onclick="openTab('tweets', this)">Tweets</div>
                <div class="tab-item" onclick="openTab('friends', this)">Friends</div>
                <div class="tab-item" onclick="openTab('media', this)">Media</div>
                <div class="tab-item" onclick="openTab('likes', this)">Likes</div>
            </div>

            <div class="grid" style="grid-template-columns: 1fr;">
                <div id="view-tweets" class="tab-content">
                    {% for post in my_posts %}
                    <div class="card" style="padding-bottom:10px;">
                        <div class="tweet-header">
                            <div class="tweet-avatar" style="width:40px; height:40px; overflow:hidden; border-radius:50%;">
                                <img src="{{ user.avatar }}" style="width:100%; height:100%; object-fit:cover;">
                            </div>
                            <div>
                                <strong>{{ user.name }}</strong> <span style="color:var(--sub);">@{{ user.username }} · {{ post.date }}</span>
                            </div>
                        </div>
                        <div style="padding-left:50px;">
                            <p style="margin-top:5px;">{{ post.content }}</p>
                            <div class="tweet-actions" style="justify-content: flex-start; gap: 20px;">
                                <a href="/post_detail/{{ post.id }}" class="tweet-action-btn blue">💬 {{ post.comments_count }}</a>
                                <a href="/like_post/{{ post.id }}" class="tweet-action-btn red">♥ {{ post.likes }}</a>
                            </div>
                        </div>
                    </div>
                    {% else %}
                        <div class="card" style="text-align:center; padding:40px;">
                            <p style="color:var(--sub);">No tweets yet.</p>
                            <a href="/forum" class="btn btn-blue">Make your first tweet</a>
                        </div>
                    {% endfor %}
                </div>

                <div id="view-friends" class="tab-content" style="display:none;">
                    <div class="card">
                        <h3 style="margin-top:0;">My Friends ({{ friends_list|length }})</h3>
                        {% if friends_list %}
                            {% for friend in friends_list %}
                            <div class="friend-row">
                                <div style="display:flex; gap:10px; align-items:center;">
                                    <div class="tweet-avatar" style="width:35px; height:35px; overflow:hidden; border-radius:50%;">
                                        <img src="{{ friend.avatar }}" style="width:100%; height:100%; object-fit:cover;">
                                    </div>
                                    <div>
                                        <div style="font-weight:700; font-size:0.9rem;">{{ friend.name }}</div>
                                        <div style="font-size:0.8rem; color:var(--sub);">@{{ friend.username }}</div>
                                    </div>
                                </div>
                                <a href="/chat/{{ friend.id }}" class="btn btn-blue" style="padding:6px 15px; font-size:0.8rem;">Message</a>
                            </div>
                            {% endfor %}
                        {% else %}
                            <p style="color:var(--sub);">No friends yet. <a href="/match">Go match up!</a></p>
                        {% endif %}
                    </div>
                </div>
                <div id="view-media" class="tab-content" style="display:none;"><div class="card" style="text-align:center; padding:40px; color:var(--sub);">No media uploaded.</div></div>
                <div id="view-likes" class="tab-content" style="display:none;"><div class="card" style="text-align:center; padding:40px; color:var(--sub);">No likes yet.</div></div>
            </div>
        </div>

        <div id="edit-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:999;">
            <div class="card" style="max-width:400px; margin:100px auto; max-height: 80vh; overflow-y: auto;">
                <h2>Edit Profile</h2>
                <form method="POST">
                    <label>Choose Avatar</label>
                    <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 20px; padding: 10px; background: #f8f9fa; border-radius: 8px;">
                        {% for av in avatars %}
                        <label style="cursor: pointer; text-align: center;">
                            <input type="radio" name="avatar_url" value="{{ av }}" style="display: none;" 
                                   {% if user.avatar == av %}checked{% endif %} onchange="highlightAvatar(this)">
                            <img src="{{ av }}" class="avatar-choice" 
                                 style="width: 70px; height: 70px; border-radius: 50%; border: 3px solid {% if user.avatar == av %}var(--blue){% else %}transparent{% endif %}; transition: 0.2s;">
                        </label>
                        {% endfor %}
                    </div>

                    <label>Program</label>
                    <input type="text" name="program" value="{{ user.program }}">
                    <label>Interests (comma separated)</label>
                    <input type="text" name="interests" value="{{ user.interests|join(',') }}">
                    <label>Bio</label>
                    <textarea name="bio">{{ user.bio }}</textarea>
                    
                    <div style="text-align:right; margin-top:10px;">
                        <button type="button" onclick="document.getElementById('edit-modal').style.display='none'" class="btn btn-outline">Cancel</button>
                        <button class="btn btn-blue">Save Changes</button>
                    </div>
                </form>
            </div>
        </div>

        <script>
        function openTab(tabName, elm) {
            document.querySelectorAll('.tab-content').forEach(d => d.style.display = 'none');
            document.getElementById('view-' + tabName).style.display = 'block';
            document.querySelectorAll('.tab-item').forEach(t => t.classList.remove('tab-active'));
            elm.classList.add('tab-active');
        }

        function highlightAvatar(input) {
            document.querySelectorAll('.avatar-choice').forEach(img => {
                img.style.borderColor = 'transparent';
            });
            input.nextElementSibling.style.borderColor = 'var(--blue)';
        }
        </script>
    """
    return render_page(content, user=user, my_posts=my_posts, friends_list=friends_list, avatars=AVATAR_OPTIONS)
    
@app.route('/book_appointment', methods=['GET', 'POST'])
def book_appointment():
    user = get_user_by_id(session['user_id'])
    
    # Pre-defined slots for the dropdown
    time_slots = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"]

    if request.method == 'POST':
        cid = int(request.form['cid']) 
        date_str = request.form['date'] # Format YYYY-MM-DD
        time_str = request.form['time'] # Format HH:MM
        reason = request.form['reason']
        
        full_datetime = f"{date_str} {time_str}:00"

        # Check if slot is taken
        existing = query_db("SELECT * FROM CounselorAppointment WHERE counselor_id=%s AND appointment_date=%s AND status != 'Declined'", (cid, full_datetime), one=True)
        
        if existing:
            flash("⚠️ That slot is already booked. Please choose another.")
            return redirect('/book_appointment')

        execute_db("""
            INSERT INTO CounselorAppointment (student_id, counselor_id, appointment_date, reason) 
            VALUES (%s, %s, %s, %s)
        """, (user['student_id'], cid, full_datetime, reason))
        
        flash("Requested.")
        return redirect('/dashboard')
    
    counselors = query_db("SELECT * FROM Counselor")
    
    content = """
        <div class="card" style="max-width:500px; margin:0 auto;">
            <h2>Book Counselor</h2>
            <form method="POST">
                <label>Counselor</label>
                <select name="cid" required>
                    {% for c in counselors %}
                        <option value="{{ c.counselor_id }}">{{ c.full_name }} ({{ c.specialization }})</option>
                    {% endfor %}
                </select>
                
                <label>Date</label>
                <input type="date" name="date" required min="{{ now }}">
                
                <label>Available Time Slot</label>
                <select name="time" required>
                    {% for t in slots %}
                        <option value="{{ t }}">{{ t }}</option>
                    {% endfor %}
                </select>
                <small style="color:var(--sub); display:block; margin-bottom:10px;">Note: If a slot is actually taken, the system will alert you when you submit the booking appointment.</small>

                <label>Reason</label>
                <textarea name="reason" placeholder="Briefly describe your concern..." required></textarea>
                <button class="btn" style="width:100%">Book Session</button>
            </form>
        </div>
    """
    return render_page(content, counselors=counselors, slots=time_slots, now=datetime.now().strftime('%Y-%m-%d'))

# ==========================================
# ADMIN FEATURES 
# ==========================================
def admin_dashboard():
    # --- 1. METRICS DATA ---
    total_counselors = query_db("SELECT COUNT(*) as c FROM Counselor", one=True)['c']
    
    # Active assignments (active cases)
    active_cases = query_db("""
        SELECT COUNT(DISTINCT student_id) as c FROM (
            SELECT student_id FROM Assignment WHERE status='Accepted'
            UNION
            SELECT student_id FROM CounselorAppointment WHERE status='Confirmed'
        ) as all_active
    """, one=True)['c']
    
    # Average caseload
    avg_load = round(active_cases / total_counselors, 1) if total_counselors > 0 else 0

    # --- 2. FETCH COUNSELORS & LOADS (FIXED) ---
    raw_counselors = query_db("SELECT * FROM Counselor")
    counselors = []

    for row in raw_counselors:
        # Convert row to a standard mutable dictionary to avoid 'no attribute' errors
        c = dict(row)
        
        # Count active assignments for this specific counselor
        cnt = query_db("""
            SELECT COUNT(DISTINCT student_id) as c FROM (
                SELECT student_id FROM Assignment WHERE counselor_id = %s AND status='Accepted'
                UNION
                SELECT student_id FROM CounselorAppointment WHERE counselor_id = %s AND status='Confirmed'
            ) as combined
        """, (c['counselor_id'], c['counselor_id']), one=True)
        
        c['load'] = cnt['c'] if cnt else 0
        c['name'] = c['full_name']
        
        # Determine status
        c['status'] = 'Available' if c['load'] < 5 else 'Full Capacity'
        c['status_color'] = 'green' if c['load'] < 5 else 'red'
        
        counselors.append(c)

    # --- 3. MOOD ALERTS ---
    alerts = query_db("""
        SELECT 
            s.student_id, s.full_name, s.account_id,
            AVG(m.mood_level) as avg_mood,
            COUNT(m.checkin_id) as total_logs,
            MAX(m.checkin_date) as last_checkin,
            (AVG(m.mood_level) / 7) * 100 as wellness_percentage
        FROM MoodCheckIn m
        JOIN Student s ON m.student_id = s.student_id
        GROUP BY s.student_id
        HAVING wellness_percentage < 30
    """)
    
    # Process alerts to see if they are already assigned
    for a in alerts:
        # Check assignments
        assigned = query_db("SELECT * FROM Assignment WHERE student_id = %s", (a['student_id'],), one=True)
        # Check appointments
        booked = query_db("SELECT * FROM CounselorAppointment WHERE student_id = %s AND status IN ('Confirmed', 'Pending')", (a['student_id'],), one=True)
        
        a['is_assigned'] = bool(assigned or booked)
        a['percentage'] = int(a['wellness_percentage'])
        a['avg_mood'] = round(a['avg_mood'], 1)

    # --- 4. APPOINTMENT REQUESTS ---
    appt_requests = query_db("""
        SELECT ca.*, s.full_name as student_name, s.score_percentage, c.full_name as requested_counselor
        FROM CounselorAppointment ca
        JOIN Student s ON ca.student_id = s.student_id
        JOIN Counselor c ON ca.counselor_id = c.counselor_id
        WHERE ca.status = 'Pending'
        ORDER BY ca.appointment_date ASC
    """)

# --- 5. MODERATION & FLAGS ---
    
    # 1. Fetch BOTH Pending and Escalated reports
    reports = query_db("SELECT * FROM Report WHERE status IN ('Pending', 'Escalated') ORDER BY created_at ASC")
    
    # 2. Process them (Add names, content, priority)
    for r in reports:
        # A. Fetch Content & Author
        r['content_preview'] = "Content deleted or unavailable"
        r['reported_user_id'] = None
        r['reported_user_name'] = "Unknown"
        
        if r['target_type'] == 'post':
            p = query_db("SELECT p.content, p.student_id, s.full_name FROM Post p JOIN Student s ON p.student_id=s.student_id WHERE post_id = %s", (r['target_id'],), one=True)
            if p: 
                r['content_preview'] = p['content']
                r['reported_user_id'] = p['student_id']
                r['reported_user_name'] = p['full_name']
        elif r['target_type'] == 'comment':
            c = query_db("SELECT c.content, c.student_id, s.full_name FROM Comment c JOIN Student s ON c.student_id=s.student_id WHERE comment_id = %s", (r['target_id'],), one=True)
            if c: 
                r['content_preview'] = c['content']
                r['reported_user_id'] = c['student_id']
                r['reported_user_name'] = c['full_name']

        # B. Get Reporter Name 
        reporter = query_db("SELECT username FROM Account WHERE account_id=%s", (r['reporter_id'],), one=True)
        r['reporter_name'] = reporter['username'] if reporter else "Unknown"

        # C. Priority Logic
        if r['status'] == 'Escalated':
            r['priority'] = 'CRITICAL'
            r['border_color'] = 'red'
            r['badge_color'] = 'red'
            r['alert_msg'] = "🚨 MODERATOR VERIFIED VIOLATION"
        else:
            severe_keywords = ['harassment', 'threat', 'self-harm', 'severe']
            is_high = any(k in r['reason'].lower() for k in severe_keywords)
            r['priority'] = 'High' if is_high else 'Normal'
            r['border_color'] = 'orange' if is_high else '#ddd'
            r['badge_color'] = 'orange' if is_high else '#777'
            r['alert_msg'] = ""

    # 3. Sort: Escalated (Critical) First
    reports.sort(key=lambda x: 0 if x.get('status') == 'Escalated' else 1)

    # ... (Flags logic follows this) ...
    flags = query_db("SELECT f.*, s.full_name as s_name, s.score_percentage as s_score FROM FlagAccount f JOIN Student s ON f.student_id=s.student_id WHERE f.status='Pending'")

    # --- SCORING TAB DATA PREP ---
    # Fetch restricted users with their active appeals and violation history
    restricted_users = query_db("""
        SELECT s.*, a.username 
        FROM Student s 
        JOIN Account a ON s.account_id = a.account_id 
        WHERE s.points < %s AND a.is_active = 1 
    """, (CONFIG['restriction_threshold'],))

    for u in restricted_users:
        u['name'] = u['full_name']
        
        # 1. Get Active Appeal
        u['active_appeal'] = query_db("SELECT * FROM Appeal WHERE student_id = %s AND status='Pending'", (u['student_id'],), one=True)
        
        # 2. Get Violation History (Resolved Reports against this user)
        # This joins Reports to Posts/Comments to find violations by this student
        u['history'] = query_db("""
            SELECT r.reason, r.created_at, 'Violation' as type
            FROM Report r
            LEFT JOIN Post p ON r.target_type='post' AND r.target_id=p.post_id
            LEFT JOIN Comment c ON r.target_type='comment' AND r.target_id=c.comment_id
            WHERE r.status='Resolved' AND (p.student_id=%s OR c.student_id=%s)
            ORDER BY r.created_at DESC
        """, (u['student_id'], u['student_id']))

    suspended_users = query_db("""
        SELECT s.*, a.username, a.is_active,
        (SELECT reason FROM Appeal WHERE student_id = s.student_id AND status='Pending' LIMIT 1) as appeal_reason,
        (SELECT appeal_id FROM Appeal WHERE student_id = s.student_id AND status='Pending' LIMIT 1) as appeal_id
        FROM Student s 
        JOIN Account a ON s.account_id = a.account_id 
        WHERE a.is_active = 0
    """)

    # --- HTML CONTENT ---
    content = """
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
        <h1>Admin Command Center</h1>
        <div style="font-size:0.9rem; color:var(--sub);">{{ now }}</div>
    </div>

    <div style="display:flex; gap:20px; border-bottom:1px solid #ddd; margin-bottom:20px;">
        <div class="tab-item tab-active" onclick="openTab('counselors', this)">🧑‍⚕️ Counselors & Appts</div>
        <div class="tab-item" onclick="openTab('alerts', this)">🚨 Mood Alerts & Assign</div>
        <div class="tab-item" onclick="openTab('reports', this)">🛡️ Moderation</div>
        <div class="tab-item" onclick="openTab('scoring', this)">⚖️ Scoring</div>
        <div class="tab-item" onclick="openTab('suspended', this)" style="color:var(--red);">⛔ Suspended</div>
    </div>
    <div id="view-suspended" class="tab-content" style="display:none;">
        <div class="card" style="border-top: 5px solid var(--red);">
            <h3>⛔ Suspended Accounts</h3>
            {% if suspended_users %}
                <table style="width:100%">
                    <tr><th>User</th><th>Program</th><th>Appeal</th><th>Action</th></tr>
                    {% for u in suspended_users %}
                    <tr>
                        <td><strong>{{ u.full_name }}</strong><br><small>@{{ u.username }}</small></td>
                        <td>{{ u.program }}</td>
                        <td>
                            {% if u.appeal_reason %}
                                <div style="background:#fff8e1; padding:5px; font-size:0.8rem;">"{{ u.appeal_reason }}"</div>
                            {% else %}<span style="color:#ccc;">None</span>{% endif %}
                        </td>
                        <td>
                            <form action="/admin/restore_user" method="POST" onsubmit="return confirm('Restore user?')">
                                <input type="hidden" name="student_id" value="{{ u.student_id }}">
                                {% if u.appeal_id %}<input type="hidden" name="appeal_id" value="{{ u.appeal_id }}">{% endif %}
                                <button class="btn btn-sm btn-green">Restore</button>
                            </form>
                        </td>
                    </tr>
                    {% endfor %}
                </table>
            {% else %}
                <p style="text-align:center; padding:20px; color:var(--sub);">No suspended users.</p>
            {% endif %}
        </div>
    </div>
    <div id="view-scoring" class="tab-content" style="display:none;">
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:25px;">
            
            <div>
                <h3 style="margin-top:0;">⚙️ Scoring Configuration</h3>
                <form action="/admin/update_scoring_config" method="POST">
                    <div class="card" style="border-top: 5px solid var(--green); background:#f0fff4;">
                        <h4 style="color:var(--green); margin-top:0;">Positive Contributions (+)</h4>
                        <label>Post Creation</label><input type="number" name="score_post" value="{{ config.score_post }}">
                        <label>Helpful Answer</label><input type="number" name="score_helpful" value="{{ config.score_helpful }}">
                        <label>Peer Support</label><input type="number" name="score_support" value="{{ config.score_support }}">
                    </div>
                    <div class="card" style="border-top: 5px solid var(--red); background:#fff5f5; margin-top:15px;">
                        <h4 style="color:var(--red); margin-top:0;">Violations & Penalties (-)</h4>
                        <label>Content Removal</label><input type="number" name="penalty_removal" value="{{ config.penalty_removal }}">
                        <label>Harassment</label><input type="number" name="penalty_harassment" value="{{ config.penalty_harassment }}">
                        <label>Severe Violation</label><input type="number" name="penalty_severe" value="{{ config.penalty_severe }}">
                    </div>
                    <button class="btn btn-blue" style="width:100%; margin-top:15px;">Save Configuration</button>
                </form>
            </div>

            <div>
                <h3 style="margin-top:0;">🚫 Restricted Users (< 60 points)</h3>
                <div class="card">
                    {% if restricted_users %}
                        <table style="width:100%">
                            <tr><th>User</th><th>Score</th><th>Action</th></tr>
                            {% for u in restricted_users %}
                            <tr>
                                <td>
                                    <strong>{{ u.name }}</strong><br>
                                    <small>Violations: {{ u.violations }}</small>
                                </td>
                                <td><span class="badge" style="background:var(--red); color:white;">{{ u.score_percentage }}%</span></td>
                                <td>
                                    <div style="display:flex; gap:5px;">
                                        <button onclick="openSuspendModal('{{ u.student_id }}', '{{ u.name }}', '{{ u.score_percentage }}', '{{ u.violations }}')" class="btn btn-sm btn-red">Suspend</button>
                                        
                                        {% if u.active_appeal %}
                                            <button onclick='openAppealModal({{ u|tojson }})' class="btn btn-sm btn-blue">Review Appeal</button>
                                        {% endif %}
                                    </div>
                                </td>
                            </tr>
                            {% endfor %}
                        </table>
                    {% else %}
                        <p style="text-align:center; padding:20px; color:var(--sub);">All users in good standing.</p>
                    {% endif %}
                </div>
            </div>
        </div>
    </div>

    <div id="suspend-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:1000;">
        <div class="card" style="max-width:400px; margin:100px auto;">
            <h3>Suspend User</h3>
            <p><strong>User:</strong> <span id="susp-name"></span></p>
            <p>Current Score: <span id="susp-score"></span>% (Violations: <span id="susp-vio"></span>)</p>
            
            <form action="/admin/suspend_user" method="POST" onsubmit="return confirm('Confirm Suspension? User will be blocked.');">
                <input type="hidden" name="student_id" id="susp-id">
                
                <label>Duration</label>
                <select name="duration">
                    <option value="7">7 Days</option>
                    <option value="14">14 Days</option>
                    <option value="30">30 Days</option>
                    <option value="Indefinite">Indefinite</option>
                </select>
                
                <label>Reason</label>
                <select name="reason">
                    <option>Repeated Violations</option>
                    <option>Refused to improve</option>
                    <option>Harmful Behavior</option>
                </select>
                
                <div style="text-align:right; margin-top:15px;">
                    <button type="button" onclick="document.getElementById('suspend-modal').style.display='none'" class="btn btn-outline">Cancel</button>
                    <button class="btn btn-red">Confirm Suspension</button>
                </div>
            </form>
        </div>
    </div>

    <div id="appeal-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:1000;">
        <div class="card" style="max-width:500px; margin:50px auto;">
            <h3>Review Appeal</h3>
            <div style="background:#f9f9f9; padding:10px; border-radius:5px; margin-bottom:10px;">
                <strong>User Appeal:</strong>
                <p id="app-text" style="font-style:italic;"></p>
            </div>
            
            <h4>Behavioral History</h4>
            <div id="app-history" style="max-height:150px; overflow-y:auto; border:1px solid #eee; padding:5px; font-size:0.85rem; margin-bottom:15px;">
                </div>

            <form action="/admin/process_appeal" method="POST">
                <input type="hidden" name="appeal_id" id="app-id">
                <input type="hidden" name="student_id" id="app-sid">
                
                <label>Decision</label>
                <select name="decision" onchange="toggleDenyReason(this.value)">
                    <option value="approve">Approve (Restore to 60%)</option>
                    <option value="deny">Deny (Extend Restriction)</option>
                </select>
                
                <div id="deny-reason-box" style="display:none;">
                    <label>Denial Reason / Explanation</label>
                    <textarea name="admin_note" placeholder="Explain why appeal is denied..."></textarea>
                </div>

                <div style="text-align:right; margin-top:15px;">
                    <button type="button" onclick="document.getElementById('appeal-modal').style.display='none'" class="btn btn-outline">Cancel</button>
                    <button class="btn btn-blue">Submit Decision</button>
                </div>
            </form>
        </div>
    </div>

    <script>
    
    function openModModal(id, name, reason, type, sid) {
        document.getElementById('mod-action-modal').style.display = 'block';
        document.getElementById('mod-report-id').value = id;
        document.getElementById('mod-user').innerText = name;
        document.getElementById('mod-reason').innerText = reason;
        document.getElementById('mod-target-type').value = type;
        document.getElementById('mod-student-id').value = sid;
    }

    function openSuspendModal(id, name, score, vio) {
        document.getElementById('suspend-modal').style.display = 'block';
        document.getElementById('susp-id').value = id;
        document.getElementById('susp-name').innerText = name;
        document.getElementById('susp-score').innerText = score;
        document.getElementById('susp-vio').innerText = vio;
    }

    function openAppealModal(user) {
        document.getElementById('appeal-modal').style.display = 'block';
        document.getElementById('app-id').value = user.active_appeal.appeal_id;
        document.getElementById('app-sid').value = user.student_id;
        document.getElementById('app-text').innerText = user.active_appeal.reason;
        
        let histHtml = "";
        if(user.history.length > 0) {
            user.history.forEach(h => {
                histHtml += `<div style='border-bottom:1px solid #eee; padding:5px;'>❌ ${h.reason} <span style='color:#999; float:right'>${h.created_at}</span></div>`;
            });
        } else {
            histHtml = "No recent history found.";
        }
        document.getElementById('app-history').innerHTML = histHtml;
    }

    function toggleDenyReason(val) {
        document.getElementById('deny-reason-box').style.display = (val === 'deny') ? 'block' : 'none';
    }

    function openTab(tabName, elm) {
        document.querySelectorAll('.tab-content').forEach(d => d.style.display = 'none');
        document.getElementById('view-' + tabName).style.display = 'block';
        document.querySelectorAll('.tab-item').forEach(t => t.classList.remove('tab-active'));
        elm.classList.add('tab-active');
    }

    const counselorLoads = {
        {% for c in counselors %}
            "{{ c.counselor_id }}": {{ c.load }},
        {% endfor %}
    };

    function validateAssignment(form) {
        const counselorId = form.counselor_id.value;
        const currentLoad = counselorLoads[counselorId] || 0;

        if (currentLoad >= 5) {
            alert("❌ Assignment Failed: This counselor has reached the maximum capacity of 5 students. Please select another available counselor.");
            return false; // This stops the form from submitting
        }
        return confirm('Confirm counselor assignment?');
    }
    </script>

    <div id="view-counselors" class="tab-content">
        <div class="grid" style="grid-template-columns: repeat(4, 1fr); margin-bottom:20px;">
            <div class="card" style="text-align:center; padding:15px;">
                <div style="font-size:2rem; font-weight:bold;">{{ total_counselors }}</div>
                <div style="color:var(--sub); font-size:0.85rem;">Total Counselors</div>
            </div>
            <div class="card" style="text-align:center; padding:15px;">
                <div style="font-size:2rem; font-weight:bold; color:var(--blue);">{{ active_cases }}</div>
                <div style="color:var(--sub); font-size:0.85rem;">Active Cases</div>
            </div>
            <div class="card" style="text-align:center; padding:15px;">
                <div style="font-size:2rem; font-weight:bold;">{{ avg_load }}</div>
                <div style="color:var(--sub); font-size:0.85rem;">Avg Caseload</div>
            </div>
            <div class="card" style="text-align:center; padding:15px;">
                <div style="font-size:2rem; font-weight:bold; color:var(--green);">100%</div>
                <div style="color:var(--sub); font-size:0.85rem;">Response Rate</div>
            </div>
        </div>

        <div class="card" style="border-left:4px solid var(--orange); margin-bottom:25px;">
            <h3>📅 Pending Appointment Requests</h3>
            {% if appt_requests %}
                <table style="width:100%">
                    <tr>
                        <th>Student</th>
                        <th>Wellness</th>
                        <th>Requested Date</th>
                        <th>Reason</th>
                        <th>Requested Counselor</th>
                        <th>Action</th>
                    </tr>
                    {% for r in appt_requests %}
                    <tr>
                        <td><strong>{{ r.student_name }}</strong></td>
                        <td style="color:{{ 'red' if r.score_percentage < 50 else 'green' }}">{{ r.score_percentage }}%</td>
                        <td>{{ r.appointment_date }}</td>
                        <td>{{ r.reason }}</td>
                        <td>{{ r.requested_counselor }}</td>
                        <td>
                            <form action="/admin/confirm_appt" method="POST" style="display:flex; gap:5px;">
                                <input type="hidden" name="appt_id" value="{{ r.appointment_id }}">
                                
                                <select name="final_counselor_id" style="padding:5px; border-radius:4px; border:1px solid #ccc; width:120px;">
                                    <option value="{{ r.counselor_id }}" selected>Confirm Current</option>
                                    {% for c in counselors %}
                                        {% if c.counselor_id != r.counselor_id %}
                                            <option value="{{ c.counselor_id }}">Reassign: {{ c.name }}</option>
                                        {% endif %}
                                    {% endfor %}
                                </select>
                                <button class="btn btn-sm btn-green">✓</button>
                            </form>
                        </td>
                    </tr>
                    {% endfor %}
                </table>
            {% else %}
                <p style="color:var(--sub);">No pending appointment requests.</p>
            {% endif %}
        </div>

        <h3>Counselor Availability</h3>
        <div class="grid">
            {% for c in counselors %}
            <div class="card">
                <div style="display:flex; justify-content:space-between;">
                    <h3>{{ c.name }}</h3>
                    <span class="badge" style="background:{{ c.status_color }}; color:white;">{{ c.status }}</span>
                </div>
                <p style="color:var(--sub);">{{ c.specialization }}</p>
                <div style="margin-top:10px; font-weight:bold;">
                    Current Caseload: {{ c.load }} / 5
                </div>
                <div style="background:#eee; height:6px; border-radius:3px; margin-top:5px; width:100%;">
                    <div style="background:var(--blue); height:100%; border-radius:3px; width:{{ (c.load/5)*100 }}%;"></div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <div id="view-alerts" class="tab-content" style="display:none;">
        <div class="card">
            <h3>🚨 Students Requiring Attention (Score < 30%)</h3>
            <table style="width:100%">
                <tr>
                    <th>Student Details</th>
                    <th>Alert Severity</th>
                    <th>Last Active</th>
                    <th>Assignment Action</th>
                </tr>
                {% for a in alerts %}
                <tr style="border-bottom:1px solid #eee;">
                    <td>
                        <strong>{{ a.full_name }}</strong><br>
                        <small>Logs: {{ a.total_logs }}</small>
                    </td>
                    <td>
                        <span class="badge" style="background:#ffe5e5; color:red; font-size:1rem;">
                            {{ a.percentage }}% (Critical)
                        </span>
                    </td>
                    <td>{{ a.last_checkin }}</td>
                    <td>
                        {% if not a.is_assigned %}
                            <form action="/admin/assign_counselor" method="POST" style="background:#f9f9f9; padding:10px; border-radius:8px;" onsubmit="return validateAssignment(this)">
                                <input type="hidden" name="student_id" value="{{ a.student_id }}">
                                
                                <label style="font-size:0.8rem; font-weight:bold;">Select Counselor:</label>
                                <select name="counselor_id" required style="margin-bottom:5px;">
                                    <option value="">-- Choose based on capacity --</option>
                                    {% for c in counselors %}
                                        <option value="{{ c.counselor_id }}" {% if c.load >= 5 %}disabled{% endif %}>
                                            {{ c.name }} (Load: {{ c.load }}) {% if c.load >= 5 %}[FULL]{% endif %}
                                        </option>
                                    {% endfor %}
                                </select>
                                <button class="btn btn-sm btn-blue" style="width:100%;">Confirm Assignment</button>
                            </form>
                        {% else %}
                            <span class="badge" style="background:var(--green); color:white;">✓ Assigned/Booked</span>
                        {% endif %}
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="4" style="text-align:center; padding:20px;">No critical alerts.</td></tr>
                {% endfor %}
            </table>
        </div>
    </div>

<div id="view-reports" class="tab-content" style="display:none;">
        <div class="card">
            <h3>Moderation Queue</h3>
            {% if reports %}
                {% for r in reports %}
                <div style="border: 2px solid {{ r.border_color }}; border-radius: 8px; padding: 15px; margin-bottom: 15px; background: #fff;">
                    
                    {% if r.alert_msg %}
                    <div style="background: {{ r.badge_color }}; color: white; padding: 5px 10px; border-radius: 4px; font-weight: bold; margin-bottom: 10px; font-size: 0.85rem;">
                        {{ r.alert_msg }}
                    </div>
                    {% endif %}

                    <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                        <div>
                            <span class="badge" style="background:{{ r.badge_color }}; color:white;">{{ r.priority }} Priority</span>
                            <span class="badge">{{ r.target_type|upper }}</span>
                        </div>
                        <small style="color:var(--sub);">{{ r.created_at }}</small>
                    </div>                    
                    <p><strong>Reported User:</strong> {{ r.reported_user_name }}</p>
                    <p><strong>Violation Type:</strong> {{ r.reason }}</p>
                    <div style="background:#f9f9f9; padding:10px; border-left:3px solid var(--blue); margin:10px 0; font-style:italic;">
                        "{{ r.content_preview }}"
                    </div>
                    
                    <div style="text-align:right;">
                        <button onclick="openModModal('{{ r.report_id }}', '{{ r.reported_user_name }}', '{{ r.reason }}', '{{ r.target_type }}', '{{ r.reported_user_id }}')" class="btn btn-sm btn-blue">Review & Act</button>
                    </div>
                </div>
                {% endfor %}
            {% else %}<p style="color:var(--sub); padding:20px;">No pending reports.</p>{% endif %}
        </div>
        
        <div class="card" style="margin-top:20px;">
            <h3>Flagged Students</h3>
            {% if flags %}
                <table>
                    <tr><th>Student</th><th>Score</th><th>Reason</th><th>Action</th></tr>
                    {% for f in flags %}
                    <tr>
                        <td>{{ f.s_name }}</td>
                        <td>{{ f.s_score }}</td>
                        <td>{{ f.reason }}</td>
                        <td>
                            <form action="/admin/handle_flag/{{ f.student_id }}/suspend" method="POST">
                                <button class="btn btn-sm btn-red">Suspend</button>
                            </form>
                        </td>
                    </tr>
                    {% endfor %}
                </table>
            {% else %}<p>No flags.</p>{% endif %}
        </div>
    </div>

    <div id="mod-action-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:1000;">
        <div class="card" style="max-width:500px; margin:50px auto;">
            <h3>Evaluate Violation</h3>
            <p><strong>User:</strong> <span id="mod-user"></span></p>
            <p><strong>Reported Reason:</strong> <span id="mod-reason"></span></p>
            
            <form action="/admin/resolve_report_action" method="POST" onsubmit="return confirm('Confirm penalty and action?');">
                <input type="hidden" name="report_id" id="mod-report-id">
                <input type="hidden" name="target_student_id" id="mod-student-id">
                <input type="hidden" name="target_type" id="mod-target-type">
                
                <label>Select Severity & Action:</label>
                <select name="action_code" required style="padding:10px; font-size:1rem; margin-bottom:15px;">
                    <option value="dismiss">Dismiss Report (No Violation)</option>
                    <option value="warn">Warn User (First Minor Violation)</option>
                    <option value="remove_15">Remove Content - Minor (-15 pts)</option>
                    <option value="remove_30">Remove Content - Moderate/Harassment (-30 pts)</option>
                    <option value="remove_50">Remove Content - Severe/Threat (-50 pts)</option>
                </select>
                
                <div style="text-align:right;">
                    <button type="button" onclick="document.getElementById('mod-action-modal').style.display='none'" class="btn btn-outline">Cancel</button>
                    <button class="btn btn-red">Confirm Action</button>
                </div>
            </form>
        </div>
    </div>

    <script>
    function openTab(tabName, elm) {
        document.querySelectorAll('.tab-content').forEach(d => d.style.display = 'none');
        document.getElementById('view-' + tabName).style.display = 'block';
        document.querySelectorAll('.tab-item').forEach(t => t.classList.remove('tab-active'));
        elm.classList.add('tab-active');
    }
    </script>
    """
    
    return render_page(content, 
        total_counselors=total_counselors,
        active_cases=active_cases,
        avg_load=avg_load,
        counselors=counselors,
        alerts=alerts,
        appt_requests=appt_requests,
        reports=reports,
        flags=flags,
        restricted_users=restricted_users,
        suspended_users=suspended_users,
        config=CONFIG,
        now=datetime.now().strftime("%Y-%m-%d")
    )

# ===============================
# ADMIN FEATURES 
# ===============================

@app.route('/admin/assign_counselor', methods=['POST'])
def assign_counselor_logic():
    sid = int(request.form['student_id'])
    cid = int(request.form['counselor_id']) # comes from the Dropdown
    
    cnt = query_db("""
        SELECT COUNT(DISTINCT student_id) as c FROM (
            SELECT student_id FROM Assignment WHERE counselor_id = %s AND status='Accepted'
            UNION
            SELECT student_id FROM CounselorAppointment WHERE counselor_id = %s AND status='Confirmed'
        ) as combined
    """, (cid, cid), one=True)
    
    if cnt and cnt['c'] >= 5:
        flash("❌ Maximum capacity reached for this counselor.")
        return redirect('/dashboard')
    
    execute_db("INSERT INTO Assignment (student_id, counselor_id, status) VALUES (%s, %s, 'Pending')", (sid, cid))
    
    s_acc = query_db("SELECT account_id FROM Student WHERE student_id=%s", (sid,), one=True)
    c_acc = query_db("SELECT account_id FROM Counselor WHERE counselor_id=%s", (cid,), one=True)
    
    add_notification(c_acc['account_id'], f"New Student Assigned by Admin")
    add_notification(s_acc['account_id'], f"Counselor assigned to you. Check dashboard.")
    
    flash("Counselor assigned. Waiting for acceptance.")
    return redirect('/dashboard')

@app.route('/admin/restore_user', methods=['POST'])
def restore_user():
    sid = request.form['student_id']
    appeal_id = request.form.get('appeal_id')
    
    # 1. Get Account ID
    student = query_db("SELECT account_id, full_name FROM Student WHERE student_id=%s", (sid,), one=True)
    
    # 2. Reactivate Account
    execute_db("UPDATE Account SET is_active = 1 WHERE account_id=%s", (student['account_id'],))
    
    # 3. If there was a pending appeal, mark it as approved
    if appeal_id:
        execute_db("UPDATE Appeal SET status='Approved' WHERE appeal_id=%s", (appeal_id,))
        
    # 4. Notify User (They can see this when they log in next)
    add_notification(student['account_id'], "Your account has been restored by the Administrator.")
    
    flash(f"User {student['full_name']} restored successfully.")
    return redirect('/dashboard')

@app.route('/admin/suspend_user', methods=['POST'])
def suspend_user():
    sid = request.form['student_id']
    duration = request.form['duration']
    reason = request.form['reason']
    
    # 1. Get Account ID to block login
    student = query_db("SELECT account_id, full_name FROM Student WHERE student_id = %s", (sid,), one=True)
    
    # 2. Block Login (is_active = 0)
    execute_db("UPDATE Account SET is_active = 0 WHERE account_id = %s", (student['account_id'],))
    
    # 3. Log the suspension (Using Notification table as a record since no new tables allowed)
    msg = f"ACCOUNT SUSPENDED. Reason: {reason}. Duration: {duration} days."
    add_notification(student['account_id'], msg)
    
    # 4. Remove from restricted list (Technically handled by UI logic, but we can set score to -1 to hide from restricted view if needed, or leave as is)
    flash(f"User {student['full_name']} suspended for {duration} days. Login blocked.")

    return redirect('/dashboard')

@app.route('/admin/process_appeal', methods=['POST'])
def process_appeal():
    decision = request.form['decision']
    appeal_id = request.form['appeal_id']
    sid = request.form['student_id']
    admin_note = request.form.get('admin_note', '')

    student = query_db("SELECT account_id FROM Student WHERE student_id=%s", (sid,), one=True)

    if decision == 'approve':
        # 1. Restore Score to 60% (Automatic threshold restoration)
        execute_db("UPDATE Student SET score_percentage = 60 WHERE student_id = %s", (sid,))
        
        # 2. Mark Appeal Approved
        execute_db("UPDATE Appeal SET status = 'Approved' WHERE appeal_id = %s", (appeal_id,))
        
        # 3. Notify User
        add_notification(student['account_id'], "Appeal APPROVED. Your score has been restored to 60%. Restrictions lifted.")
        flash("Appeal approved. User score restored to 60%.")

    elif decision == 'deny':
        # 1. Mark Appeal Denied
        execute_db("UPDATE Appeal SET status = 'Denied' WHERE appeal_id = %s", (appeal_id,))
        
        # 2. Notify User with Reason
        add_notification(student['account_id'], f"Appeal DENIED. Reason: {admin_note}. Restrictions remain.")
        flash("Appeal denied. User notified.")

    return redirect('/dashboard')

@app.route('/admin/confirm_appt', methods=['POST'])
def admin_confirm_appt():
    appt_id = request.form['appt_id']
    final_cid = request.form['final_counselor_id']
    
    # 1. Update the appointment: Set status to Confirmed and update Counselor ID (in case admin changed it)
    execute_db("""
        UPDATE CounselorAppointment 
        SET counselor_id = %s, status = 'Confirmed' 
        WHERE appointment_id = %s
    """, (final_cid, appt_id))
    
    # 2. Get IDs for Notification
    appt = query_db("SELECT student_id FROM CounselorAppointment WHERE appointment_id=%s", (appt_id,), one=True)
    c_acc = query_db("SELECT account_id FROM Counselor WHERE counselor_id=%s", (final_cid,), one=True)
    s_acc = query_db("SELECT account_id FROM Student WHERE student_id=%s", (appt['student_id'],), one=True)
    
    # 3. Send Notifications
    add_notification(c_acc['account_id'], "New appointment confirmed by Admin.")
    add_notification(s_acc['account_id'], "Your appointment request has been confirmed.")
    
    flash("Appointment confirmed and counselor notified.")
    return redirect('/dashboard')

@app.route('/admin/resolve_report_action', methods=['POST'])
def resolve_report_action():
    rid = request.form['report_id']
    sid = request.form.get('target_student_id') # Can be None/Empty string if content deleted
    action_code = request.form['action_code']
    target_type = request.form['target_type']
    
    report = query_db("SELECT * FROM Report WHERE report_id = %s", (rid,), one=True)
    if not report: return redirect('/dashboard')

    # 1. DISMISS
    if action_code == 'dismiss':
        execute_db("UPDATE Report SET status='Dismissed' WHERE report_id=%s", (rid,))
        flash("Report dismissed. No action taken.")
        return redirect('/dashboard')

    # 2. PROCESS VIOLATION (Warn or Penalty)
    penalty_points = 0
    msg_to_user = ""
    
    if action_code == 'warn':
        msg_to_user = "Warning: Your content was flagged. Please review community guidelines."
    elif action_code == 'remove_15':
        penalty_points = 15
        msg_to_user = "Violation: Content removed. 15 points deducted for guideline violation."
    elif action_code == 'remove_30':
        penalty_points = 30
        msg_to_user = "Violation: Content removed. 30 points deducted for harassment."
    elif action_code == 'remove_50':
        penalty_points = 50
        msg_to_user = "Violation: Content removed. 50 points deducted for severe violation."

# 3. APPLY PENALTY & CHECK THRESHOLD
    if sid and sid != 'None':
        # FIX: Deduct points from BOTH Score (Safety) AND Points (Gamification)
        execute_db("""
            UPDATE Student 
            SET score_percentage = GREATEST(0, score_percentage - %s), 
                points = GREATEST(0, points - %s),
                violations = violations + 1 
            WHERE student_id = %s
        """, (penalty_points, penalty_points, sid))
        
        # Check Threshold (<60%) logic
        s = query_db("SELECT score_percentage, account_id FROM Student WHERE student_id=%s", (sid,), one=True)
        if s:
            # Send Notification
            add_notification(s['account_id'], f"{msg_to_user} Current Safety Score: {s['score_percentage']}%")
            
    # 4. REMOVE CONTENT (If action implies removal)
    if 'remove' in action_code:
        if target_type == 'post':
            execute_db("DELETE FROM Post WHERE post_id = %s", (report['target_id'],))
        elif target_type == 'comment':
            execute_db("DELETE FROM Comment WHERE comment_id = %s", (report['target_id'],))

    # 5. CLOSE REPORT
    execute_db("UPDATE Report SET status='Resolved' WHERE report_id=%s", (rid,))
    flash(f"Action taken: {action_code}. Report resolved.")
    return redirect('/dashboard')

@app.route('/admin/handle_flag/<int:sid>/<action>', methods=['POST'])
def admin_handle_flag(sid, action):
    if action == 'dismiss':
        execute_db("UPDATE FlagAccount SET status='Dismissed' WHERE student_id=%s AND status='Pending'", (sid,))
        flash("Flag dismissed.")
        
    elif action == 'suspend':
        acc = query_db("SELECT account_id FROM Student WHERE student_id=%s", (sid,), one=True)
        execute_db("UPDATE Account SET is_active=FALSE WHERE account_id=%s", (acc['account_id'],))
        execute_db("UPDATE FlagAccount SET status='Suspended' WHERE student_id=%s AND status='Pending'", (sid,))
        flash(f"User suspended.")

    return redirect('/dashboard')

@app.route('/admin/update_scoring_config', methods=['POST'])
def update_scoring_config():
    # Update Positive
    CONFIG['score_post'] = int(request.form.get('score_post', 5))
    CONFIG['score_helpful'] = int(request.form.get('score_helpful', 10))
    CONFIG['score_support'] = int(request.form.get('score_support', 15))
    
    # Update Penalties (ensure they are stored as positive integers to be subtracted later)
    CONFIG['penalty_removal'] = int(request.form.get('penalty_removal', 15))
    CONFIG['penalty_harassment'] = int(request.form.get('penalty_harassment', 30))
    CONFIG['penalty_severe'] = int(request.form.get('penalty_severe', 50))
    
    flash("Scoring configuration updated successfully.")
    return redirect('/dashboard')

# ==========================================
# COUNSELOR FEATURES
# ==========================================

def counselor_dashboard():
    uid = session['user_id']
    me = get_user_by_id(uid) # Contains 'counselor_id'
    cid = me['counselor_id']
    
    search_query = request.args.get('q', '')
    
    # Fetch students who have an Accepted Assignment OR a Confirmed Appointment
    sql_students = """
        SELECT s.*, 
        (SELECT mood_level FROM MoodCheckIn WHERE student_id=s.student_id ORDER BY checkin_date DESC LIMIT 1) as last_mood_lvl,
        (SELECT severity_level FROM MoodCheckIn WHERE student_id=s.student_id ORDER BY checkin_date DESC LIMIT 1) as last_mood_sev,
        (SELECT title FROM TherapeuticActionPlan WHERE student_id=s.student_id AND status='Active') as active_plan_title
        FROM Student s
        WHERE s.student_id IN (
            SELECT student_id FROM Assignment WHERE counselor_id = %s AND status = 'Accepted'
            UNION
            SELECT student_id FROM CounselorAppointment WHERE counselor_id = %s AND status = 'Confirmed'
        )
    """
    # Note: We pass (cid, cid) because there are two placeholders now
    students_raw = query_db(sql_students, (cid, cid))
    students = []
    
    for s in students_raw:
        if search_query and (search_query.lower() not in s['full_name'].lower()): continue
        
        # Active Plan
        plan = query_db("SELECT * FROM TherapeuticActionPlan WHERE student_id=%s AND status='Active'", (s['student_id'],), one=True)
        
        students.append({
            'id': s['student_id'], # Internal ID for links
            'name': s['full_name'], 'program': s['program'],
            'last_mood': {'level': s['last_mood_lvl'], 'severity': s['last_mood_sev']} if s['last_mood_lvl'] else None,
            'active_plan': plan
        })
        
    # Assignments
    assign_reqs = query_db("""
        SELECT a.*, s.full_name as s_name 
        FROM Assignment a JOIN Student s ON a.student_id=s.student_id 
        WHERE a.counselor_id=%s AND a.status='Pending'
    """, (cid,))
    
    upcoming = query_db("""
    SELECT c.*, s.full_name as s_name 
    FROM CounselorAppointment c 
    JOIN Student s ON c.student_id = s.student_id 
    WHERE c.counselor_id = %s 
      AND c.status = 'Confirmed'
      AND c.appointment_date >= NOW()  -- ADD THIS LINE to hide past dates
    ORDER BY c.appointment_date ASC
""", (cid,))
    
    content = """
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
            <div>
                <h1>Counselor Dashboard</h1>
                <span style="color:var(--sub);">Specialization: {{ me.specialization }}</span>
            </div>
            <a href="/export_data" class="btn btn-outline">📥 Export Caseload Report</a>
        </div>

        <div class="grid">
            <div class="card" style="grid-column: span 3;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                    <h3>Active Caseload ({{ students|length }})</h3>
                    <form method="GET" style="display:flex; gap:10px; margin:0; width:300px;">
                        <input type="text" name="q" placeholder="Search student name or program..." value="{{ request.args.get('q', '') }}" style="margin:0;">
                        <button class="btn btn-sm">Search</button>
                    </form>
                </div>
                
                {% if students %}
                <table>
                    <tr><th>Student</th><th>Program</th><th>Risk Level</th><th>Active Plan</th><th>Manage</th></tr>
                    {% for s in students %}
                        <tr>
                            <td><strong>{{ s.name }}</strong></td>
                            <td>{{ s.program }}</td>
                            <td>
                                {% if s.last_mood %}
                                    <span class="badge" style="background: {{ 'var(--red)' if s.last_mood.severity == 'Critical' else 'var(--green)' }}; color:white;">
                                        {{ s.last_mood.severity }}
                                    </span>
                                {% else %}N/A{% endif %}
                            </td>
                            <td>
                                {% if s.active_plan %}
                                    <span style="color:var(--green);">Active: {{ s.active_plan.title }}</span>
                                {% else %}
                                    <span style="color:var(--sub);">No active plan</span>
                                {% endif %}
                            </td>
                            <td>
                                <a href="/student_details/{{ s.id }}" class="btn btn-sm btn-blue">Manage Case</a>
                            </td>
                        </tr>
                    {% endfor %}
                </table>
                {% else %}
                    <div style="text-align:center; padding:20px; color:var(--sub);">
                        No students found. <br>
                        {% if not search_query %}Waiting for Admin assignments.{% endif %}
                    </div>
                {% endif %}
            </div>

            <div class="card">
                <h3>New Case Assignments</h3>
                {% if assign_reqs %}
                    {% for p in assign_reqs %}
                        <div style="padding:10px 0; border-bottom:1px solid #f0f0f0;">
                            <strong>{{ p.s_name }}</strong> assigned by Admin.<br>
                            <div style="margin-top:5px;">
                                <a href="/verify_assign/{{ p.assignment_id }}/accept" class="btn btn-sm btn-green">Accept</a>
                                <a href="/verify_assign/{{ p.assignment_id }}/decline" class="btn btn-sm btn-red">Decline</a>
                            </div>
                        </div>
                    {% endfor %}
                {% else %}<p style="color:var(--sub);">No pending assignments.</p>{% endif %}
            </div>

            <div class="card" style="border-left: 4px solid var(--blue);">
                <h3>Upcoming Sessions</h3>
                {% if upcoming %}
                    {% for u in upcoming %}
                        <div style="padding:10px 0; border-bottom:1px solid #f0f0f0;">
                            <strong>{{ u.s_name }}</strong><br>
                            {{ u.appointment_date }}
                            <br><a href="/session_note/{{ u.appointment_id }}" class="btn btn-sm btn-outline" style="margin-top:5px;">Session Notes</a>
                        </div>
                    {% endfor %}
                {% else %}<p style="color:var(--sub);">No confirmed sessions.</p>{% endif %}
            </div>
        </div>
    """
    return render_page(content, me=me, students=students, assign_reqs=assign_reqs, upcoming=upcoming)

@app.route('/student_details/<int:sid>')
def student_details(sid):
    student = query_db("SELECT * FROM Student WHERE student_id = %s", (sid,), one=True)
    student['name'] = student['full_name']
    
    moods = query_db("SELECT *, DATE_FORMAT(checkin_date, '%Y-%m-%d') as date FROM MoodCheckIn WHERE student_id = %s", (sid,))
    for m in moods: m['level'] = m['mood_level']; m['severity'] = m['severity_level']
    
    plans = query_db("SELECT * FROM TherapeuticActionPlan WHERE student_id = %s", (sid,))
    templates = PLAN_TEMPLATES
    
    # --- NEW: Get current time string for the 'min' attribute ---
    now_str = datetime.now().strftime('%Y-%m-%dT%H:%M')
    # --------------------------------------------------------

    content = """
        <a href="/dashboard">← Back to Dashboard</a>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:10px;">
            <h1>Case File: {{ student.name }}</h1>
            <div>
                <button onclick="document.getElementById('schedule-modal').style.display='block'" class="btn btn-outline">📅 Schedule Session</button>
                <span class="badge" style="font-size:1rem;">ID: {{ student.student_id }}</span>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <h3>Student Profile</h3>
                <p><strong>Program:</strong> {{ student.program }}</p>
                <p><strong>Bio:</strong> {{ student.bio }}</p>
                <p><strong>Interests:</strong> {{ student.interests }}</p>
            </div>
            
            <div class="card" style="grid-column: span 2;">
                <div style="display:flex; justify-content:space-between;">
                    <h3>Therapeutic Action Plans</h3>
                    <button onclick="document.getElementById('plan-modal').style.display='block'" class="btn btn-sm btn-blue">+ New Plan</button>
                </div>
                {% if plans %}
                    <table>
                        <tr><th>Title</th><th>Goals</th><th>Status</th><th>Timeline</th><th>Action</th></tr>
                        {% for p in plans %}
                        <tr>
                            <td>{{ p.title }}</td>
                            <td>{{ p.goals }}</td>
                            <td>
                                <span class="badge" style="background:{{ 'var(--green)' if p.status == 'Active' else '#ccc' }}">{{ p.status }}</span>
                            </td>
                            <td>{{ p.timeline }}</td>
                            <td>
                                {% if p.status == 'Active' %}
                                <a href="/update_plan_status/{{ p.plan_id }}" class="btn btn-sm btn-outline">Mark Complete</a>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </table>
                {% else %}
                    <p style="color:var(--sub); margin-top:10px;">No action plans created yet.</p>
                {% endif %}
            </div>

            <div class="card" style="grid-column: span 3;">
                <h3>Mood History Tracking</h3>
                {% if moods %}
                    <table>
                        <tr><th>Date</th><th>Level</th><th>Severity</th><th>Note</th></tr>
                        {% for m in moods %}
                        <tr>
                            <td>{{ m.date }}</td>
                            <td>{{ m.level }}/5</td>
                            <td style="color:{{ 'red' if m.severity=='Critical' else 'green' }}">{{ m.severity }}</td>
                            <td>{{ m.note }}</td>
                        </tr>
                        {% endfor %}
                    </table>
                {% else %}<p>No mood logs yet.</p>{% endif %}
            </div>
        </div>

        <div id="plan-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:999;">
            <div class="card" style="max-width:500px; margin:50px auto;">
                <h2>Create Action Plan</h2>
                <div style="margin-bottom:15px; background:#f0f0f0; padding:10px; border-radius:8px;">
                    <label style="font-weight:bold;">📂 Load Template (Optional)</label>
                    <select id="templateSelector" onchange="loadTemplate()">
                        <option value="">-- Select a Template --</option>
                        {% for key, t in templates.items() %}
                            <option value="{{ key }}">{{ t.title }}</option>
                        {% endfor %}
                    </select>
                </div>
                <form action="/create_action_plan/{{ student.student_id }}" method="POST">
                    <label>Plan Title</label>
                    <input type="text" id="p_title" name="title" required>
                    <label>Measurable Goals</label>
                    <textarea id="p_goals" name="goals" required></textarea>
                    <label>Intervention Strategies</label>
                    <textarea id="p_strategies" name="strategies" required></textarea>
                    <label>Timeline</label>
                    <input type="text" id="p_timeline" name="timeline">
                    <div style="text-align:right; margin-top:10px;">
                        <button type="button" onclick="document.getElementById('plan-modal').style.display='none'" class="btn btn-outline">Cancel</button>
                        <button class="btn btn-blue">Save Plan</button>
                    </div>
                </form>
            </div>
        </div>

        <div id="schedule-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:999;">
            <div class="card" style="max-width:400px; margin:100px auto;">
                <h2>Schedule Session</h2>
                <form action="/counselor_schedule/{{ student.student_id }}" method="POST">
                    <label>Date & Time</label>
                    <input type="datetime-local" name="date" required min="{{ now_str }}">
                    
                    <label>Duration (Minutes)</label>
                    <select name="duration">
                        <option value="30">30 Minutes</option>
                        <option value="60" selected>60 Minutes</option>
                        <option value="90">90 Minutes</option>
                    </select>
                    <label>Session Type</label>
                    <select name="reason">
                        <option>Regular Check-in</option>
                        <option>Crisis Intervention</option>
                        <option>Action Plan Review</option>
                    </select>
                    <div style="text-align:right; margin-top:10px;">
                        <button type="button" onclick="document.getElementById('schedule-modal').style.display='none'" class="btn btn-outline">Cancel</button>
                        <button class="btn btn-blue">Confirm Booking</button>
                    </div>
                </form>
            </div>
        </div>
        
        <script>
            const templates = {{ templates|tojson }};
            function loadTemplate() {
                const key = document.getElementById('templateSelector').value;
                if(key && templates[key]) {
                    document.getElementById('p_title').value = templates[key].title;
                    document.getElementById('p_goals').value = templates[key].goals;
                    document.getElementById('p_strategies').value = templates[key].strategies;
                    document.getElementById('p_timeline').value = templates[key].timeline;
                }
            }
        </script>
    """
    # --- UPDATED: Pass now_str to render_page ---
    return render_page(content, student=student, moods=moods, plans=plans, templates=templates, now_str=now_str)

@app.route('/create_action_plan/<int:sid>', methods=['POST'])
def create_action_plan(sid):
    active = query_db("SELECT * FROM TherapeuticActionPlan WHERE student_id = %s AND status = 'Active'", (sid,), one=True)
    if active:
        flash("⚠️ Error: Student already has an active plan.")
        return redirect(f'/student_details/{sid}')

    execute_db("""
        INSERT INTO TherapeuticActionPlan (student_id, title, goals, strategies, timeline) 
        VALUES (%s, %s, %s, %s, %s)
    """, (sid, request.form['title'], request.form['goals'], request.form['strategies'], request.form['timeline']))
    
    flash("Plan created.")
    return redirect(f'/student_details/{sid}')

@app.route('/update_plan_status/<int:pid>')
def update_plan_status(pid):
    execute_db("UPDATE TherapeuticActionPlan SET status='Completed' WHERE plan_id=%s", (pid,))
    flash("Plan marked as completed.")
    return redirect(request.referrer)

@app.route('/counselor_schedule/<int:sid>', methods=['POST'])
def counselor_schedule(sid):
    c_user = get_user_by_id(session['user_id'])
    cid = c_user['counselor_id']
    date_str = request.form['date']
    
    # --- NEW: Check if date is in the past ---
    session_date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
    if session_date < datetime.now():
        flash("⚠️ Error: Cannot schedule sessions in the past.")
        return redirect(f'/student_details/{sid}')
    # ----------------------------------------

    execute_db("""
        INSERT INTO CounselorAppointment (student_id, counselor_id, appointment_date, duration, reason, status, notes)
        VALUES (%s, %s, %s, %s, %s, 'Confirmed', 'Scheduled by Counselor')
    """, (sid, cid, date_str, request.form['duration'], request.form['reason']))
    
    s_acc = query_db("SELECT account_id FROM Student WHERE student_id=%s", (sid,), one=True)
    add_notification(s_acc['account_id'], f"Counselor scheduled a session with you on {date_str}.")
    
    flash("Session scheduled.")
    return redirect(f'/student_details/{sid}')

@app.route('/verify_assign/<int:rid>/<action>')
def verify_assign(rid, action):
    status = 'Accepted' if action == 'accept' else 'Declined'
    execute_db("UPDATE Assignment SET status=%s WHERE assignment_id=%s", (status, rid))
    flash(f"Assignment {status}.")
    return redirect('/dashboard')

@app.route('/handle_appt/<int:aid>/<status>')
def handle_appt(aid, status):
    appt = query_db("SELECT * FROM CounselorAppointment WHERE appointment_id=%s", (aid,), one=True)
    execute_db("UPDATE CounselorAppointment SET status=%s WHERE appointment_id=%s", (status, aid))
    
    s_acc = query_db("SELECT account_id FROM Student WHERE student_id=%s", (appt['student_id'],), one=True)
    add_notification(s_acc['account_id'], f"Appointment {status}.")
    
    flash(f"Appointment {status}.")
    return redirect('/dashboard')

@app.route('/session_note/<int:aid>', methods=['GET', 'POST'])
def session_note(aid):
    appt = query_db("SELECT *, DATE_FORMAT(appointment_date, '%Y-%m-%d %H:%i') as date FROM CounselorAppointment WHERE appointment_id=%s", (aid,), one=True)
    student = query_db("SELECT full_name as name FROM Student WHERE student_id=%s", (appt['student_id'],), one=True)
    
    if request.method == 'POST':
        execute_db("UPDATE CounselorAppointment SET notes=%s WHERE appointment_id=%s", (request.form['notes'], aid))
        flash("Notes saved.")
        return redirect('/dashboard')

    content = """
        <a href="/dashboard">← Back</a>
        <div class="card" style="max-width:600px; margin:20px auto;">
            <h2>Session Notes</h2>
            <p><strong>Student:</strong> {{ student.name }}</p>
            <p><strong>Date:</strong> {{ appt.date }}</p>
            <form method="POST">
                <label>Confidential Clinical Notes:</label>
                <textarea name="notes" rows="10">{{ appt.notes or '' }}</textarea>
                <button class="btn">Save Notes</button>
            </form>
        </div>
    """
    return render_page(content, appt=appt, student=student)

@app.route('/export_data')
def export_data():
    c_user = get_user_by_id(session['user_id'])
    
    # Logic: Get my students
    sql = """
        SELECT s.full_name, s.program, 
        (SELECT severity_level FROM MoodCheckIn WHERE student_id=s.student_id ORDER BY checkin_date DESC LIMIT 1) as risk,
        (SELECT title FROM TherapeuticActionPlan WHERE student_id=s.student_id AND status='Active') as plan
        FROM Assignment a JOIN Student s ON a.student_id=s.student_id
        WHERE a.counselor_id=%s AND a.status='Accepted'
    """
    rows = query_db(sql, (c_user['counselor_id'],))
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Student Name', 'Program', 'Risk Level', 'Active Plan'])
    
    for r in rows:
        cw.writerow([r['full_name'], r['program'], r['risk'] or 'N/A', r['plan'] or 'None'])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=counselor_caseload_report.csv"
    output.headers["Content-type"] = "text/csv"
    return output

# ==========================================
# MODERATOR FEATURES
# ==========================================

def moderator_dashboard():
    # Reports
    reports = query_db("SELECT * FROM Report WHERE status='Pending'")
    for r in reports:
        if r['target_type'] == 'post':
            p = query_db("SELECT content, student_id FROM Post WHERE post_id=%s", (r['target_id'],), one=True)
            r['content'] = p['content'] if p else "Deleted"
            if p:
                s = query_db("SELECT full_name FROM Student WHERE student_id=%s", (p['student_id'],), one=True)
                r['author'] = s['full_name']
        elif r['target_type'] == 'comment':
             c = query_db("SELECT content, student_id FROM Comment WHERE comment_id=%s", (r['target_id'],), one=True)
             r['content'] = c['content'] if c else "Deleted"
             if c:
                 s = query_db("SELECT full_name FROM Student WHERE student_id=%s", (c['student_id'],), one=True)
                 r['author'] = s['full_name']

    # Flag Candidates
    candidates = query_db("SELECT full_name as name, program, violations, score_percentage as score, student_id as id FROM Student WHERE (violations > 0 OR score_percentage < 80)")
    
    # Content Manager
    recent_posts = query_db("SELECT p.post_id as id, p.content, s.full_name as author_name FROM Post p JOIN Student s ON p.student_id=s.student_id ORDER BY p.created_at DESC LIMIT 10")
    recent_comments = query_db("SELECT c.comment_id as id, c.content, s.full_name as author_name FROM Comment c JOIN Student s ON c.student_id=s.student_id ORDER BY c.created_at DESC LIMIT 10")
    active_announcements = query_db("SELECT *, DATE_FORMAT(date, '%Y-%m-%d') as date_str FROM Announcement ORDER BY date DESC")
    
    # Map 'date' for template
    for a in active_announcements: a['date'] = a['date_str']; a['id'] = a['announcement_id']

    content = """
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
        <h1>Moderator Dashboard</h1>
    </div>

    <div style="display:flex; gap:20px; border-bottom:1px solid #ddd; margin-bottom:20px;">
        <div class="tab-item tab-active" onclick="openTab('reports', this)">🚩 Report Center</div>
        <div class="tab-item" onclick="openTab('students', this)">🎓 Student Oversight</div>
        <div class="tab-item" onclick="openTab('content', this)">🗑️ Content Manager</div>
        <div class="tab-item" onclick="openTab('announcements', this)">📢 Announcements</div>
    </div>

    <div id="view-reports" class="tab-content">
        <div class="card">
            <h3>Reported Messages Queue</h3>
            {% if reports %}
                <table>
                    <tr><th>Type</th><th>Author</th><th>Content Preview</th><th>Action</th></tr>
                    {% for r in reports %}
                    <tr>
                        <td><span class="badge">{{ r.target_type|upper }}</span></td>
                        <td>{{ r.author }}</td>
                        <td>"{{ r.content[:50] }}..."</td>
                        <td>
                            <button onclick="document.getElementById('review-modal-{{ r.report_id }}').style.display='block'" class="btn btn-sm btn-blue">Review</button>
                        </td>
                    </tr>
                    
                    <div id="review-modal-{{ r.report_id }}" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:999;">
                        <div class="card" style="max-width:500px; margin:100px auto;">
                            <h3>Review Reported Message</h3>
                            <div style="background:#f9f9f9; padding:15px; border-radius:8px; margin-bottom:20px;">
                                "{{ r.content }}"
                            </div>
                            <div style="display:flex; justify-content:center; gap:20px;">
                                <form action="/mod/review_decision/{{ r.report_id }}/dismiss" method="POST"><button class="btn btn-outline">No (Dismiss)</button></form>
                                <form action="/mod/review_decision/{{ r.report_id }}/violation" method="POST" onsubmit="return confirm('Confirm Violation?')"><button class="btn btn-red">Yes (Violation)</button></form>
                            </div>
                            <div style="text-align:center; margin-top:10px;"><a href="#" onclick="document.getElementById('review-modal-{{ r.report_id }}').style.display='none'">Cancel</a></div>
                        </div>
                    </div>
                    {% endfor %}
                </table>
            {% else %}<p style="color:var(--sub); text-align:center; padding:20px;">No pending reports.</p>{% endif %}
        </div>
    </div>

    <div id="view-students" class="tab-content" style="display:none;">
        <div class="card">
            <h3>Potential Flag List</h3>
            <table>
                <tr><th>Student</th><th>Violations</th><th>Score</th><th>Action</th></tr>
                {% for s in candidates %}
                <tr>
                    <td><strong>{{ s.name }}</strong><br><span style="font-size:0.8rem;">{{ s.program }}</span></td>
                    <td>{{ s.violations }}</td>
                    <td style="color:{{ 'red' if s.score < 60 else 'black' }}">{{ s.score }}%</td>
                    <td>
                        <button onclick="document.getElementById('flag-modal-{{ s.id }}').style.display='block'" class="btn btn-sm btn-orange">🚩 Flag</button>
                    </td>
                </tr>
                <div id="flag-modal-{{ s.id }}" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:999;">
                    <div class="card" style="max-width:400px; margin:100px auto;">
                        <h3>Flag Student: {{ s.name }}</h3>
                        <form action="/mod/flag_student" method="POST">
                            <input type="hidden" name="student_id" value="{{ s.id }}">
                            <textarea name="reason" placeholder="Reason..." required rows="4"></textarea>
                            <div style="text-align:right; margin-top:15px;">
                                <button type="button" onclick="document.getElementById('flag-modal-{{ s.id }}').style.display='none'" class="btn btn-outline">Cancel</button>
                                <button class="btn btn-orange">Confirm Flag</button>
                            </div>
                        </form>
                    </div>
                </div>
                {% endfor %}
            </table>
        </div>
    </div>

    <div id="view-content" class="tab-content" style="display:none;">
        <div class="grid">
            <div class="card">
                <h3>Recent Posts</h3>
                {% for p in recent_posts %}
                <div style="border-bottom:1px solid #eee; padding:10px 0; display:flex; justify-content:space-between;">
                    <div style="font-size:0.85rem;"><strong>{{ p.author_name }}</strong>: {{ p.content }}</div>
                    <form action="/mod/delete_post_direct/{{ p.id }}" method="POST" onsubmit="return confirm('Delete post?')"><button class="btn btn-sm btn-red">Del</button></form>
                </div>
                {% endfor %}
            </div>
            <div class="card">
                <h3>Recent Comments</h3>
                {% for c in recent_comments %}
                <div style="border-bottom:1px solid #eee; padding:10px 0; display:flex; justify-content:space-between;">
                    <div style="font-size:0.85rem;"><strong>{{ c.author_name }}</strong>: {{ c.content }}</div>
                    <form action="/mod/delete_comment_direct/{{ c.id }}" method="POST" onsubmit="return confirm('Delete comment?')"><button class="btn btn-sm btn-red">Del</button></form>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>

    <div id="view-announcements" class="tab-content" style="display:none;">
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                <h3>Active Announcements</h3>
                <button onclick="document.getElementById('announce-modal').style.display='block'" class="btn btn-green">+ New Announcement</button>
            </div>
            
            {% if active_announcements %}
                <table style="width:100%;">
                    <tr>
                        <th style="text-align:left;">Date</th>
                        <th style="text-align:left;">Title</th>
                        <th style="text-align:left;">Content Preview</th>
                        <th style="text-align:right;">Action</th>
                    </tr>
                    {% for a in active_announcements %}
                    <tr>
                        <td style="color:var(--sub); font-size:0.85rem;">{{ a.date }}</td>
                        <td style="font-weight:bold;">{{ a.title }}</td>
                        <td>{{ a.content }}</td>
                        <td style="text-align:right;">
                            <form action="/mod/delete_announcement/{{ a.id }}" method="POST" onsubmit="return confirm('Are you sure you want to delete this announcement?');" style="display:inline;">
                                <button class="btn btn-sm btn-red">Delete</button>
                            </form>
                        </td>
                    </tr>
                    {% endfor %}
                </table>
            {% else %}
                <div style="text-align:center; padding:30px; border:2px dashed #eee; color:var(--sub);">
                    No active announcements.
                </div>
            {% endif %}
        </div>
    </div>

    <div id="announce-modal" style="display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.5); z-index:1000;">
        <div class="card" style="max-width:500px; margin:80px auto;">
            <h2>Make Announcement</h2>
            <form action="/mod/make_announcement" method="POST">
                <label>Title</label>
                <input type="text" name="title" required placeholder="e.g., System Maintenance">
                <label>Content</label>
                <textarea name="content" rows="5" required placeholder="Enter announcement details..."></textarea>
                <div style="text-align:right; margin-top:15px;">
                    <button type="button" onclick="document.getElementById('announce-modal').style.display='none'" class="btn btn-outline">Cancel</button>
                    <button class="btn btn-green">Confirm & Post</button>
                </div>
            </form>
        </div>
    </div>

    <script>
    function openTab(tabName, elm) {
        document.querySelectorAll('.tab-content').forEach(d => d.style.display = 'none');
        document.getElementById('view-' + tabName).style.display = 'block';
        document.querySelectorAll('.tab-item').forEach(t => t.classList.remove('tab-active'));
        elm.classList.add('tab-active');
    }
    </script>
    """
    return render_page(content, reports=reports, candidates=candidates, recent_posts=recent_posts, recent_comments=recent_comments, active_announcements=active_announcements)

@app.route('/mod/make_announcement', methods=['POST'])
def mod_make_announcement():
    execute_db("INSERT INTO Announcement (title, content) VALUES (%s, %s)", (request.form['title'], request.form['content']))
    flash("Announcement Posted!")
    return redirect('/dashboard')

@app.route('/mod/review_decision/<int:rid>/<decision>', methods=['POST'])
def mod_review_decision(rid, decision):
    mod_user = get_user_by_id(session['user_id'])
    
    if decision == 'dismiss':
        # Moderator decides it's safe - Close the report
        execute_db("UPDATE Report SET status='Dismissed' WHERE report_id=%s", (rid,))
        flash("Report dismissed.")
        
    elif decision == 'violation':
        # Moderator confirms violation - ESCALATE to Admin
        # 1. Update status to 'Escalated' so it stays active but marked
        execute_db("UPDATE Report SET status='Escalated' WHERE report_id=%s", (rid,))
        
        # 2. Notify Admin (Assuming Admin has account_id = 1, or fetch by role)
        admin = query_db("SELECT account_id FROM Account WHERE role='admin' LIMIT 1", one=True)
        if admin:
            msg = f"🚨 ALERT: Moderator {mod_user['name']} verified Report #{rid} as a VIOLATION. Please review immediately."
            add_notification(admin['account_id'], msg)
            
        flash("Violation verified. Escalated to Admin for enforcement.")

    return redirect('/dashboard')

@app.route('/mod/delete_announcement/<int:aid>', methods=['POST'])
def mod_delete_announcement(aid):
    execute_db("DELETE FROM Announcement WHERE announcement_id=%s", (aid,))
    flash("Announcement deleted.")
    return redirect('/dashboard')

@app.route('/mod/flag_student', methods=['POST'])
def mod_flag_student():
    sid = int(request.form['student_id'])
    mod_user = get_user_by_id(session['user_id'])
    mid = query_db("SELECT moderator_id FROM Moderator WHERE account_id=%s", (mod_user['id'],), one=True)['moderator_id']
    
    execute_db("INSERT INTO FlagAccount (student_id, moderator_id, reason) VALUES (%s, %s, %s)", (sid, mid, request.form['reason']))
    
    flash("Student flagged successfully.")
    return redirect('/dashboard')

@app.route('/mod/delete_post_direct/<int:pid>', methods=['POST'])
def delete_post_direct(pid):
    execute_db("DELETE FROM Post WHERE post_id=%s", (pid,))
    flash("Post deleted.")
    return redirect('/dashboard')

@app.route('/mod/delete_comment_direct/<int:cid>', methods=['POST'])
def delete_comment_direct(cid):
    execute_db("DELETE FROM Comment WHERE comment_id=%s", (cid,))
    flash("Comment deleted.")
    return redirect('/dashboard')

if __name__ == '__main__':
    app.run(debug=True, port=5000)