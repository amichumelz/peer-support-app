==============================================================================
USER GUIDE: DIGITAL PEER SUPPORT SYSTEM
==============================================================================

This document contains step-by-step instructions to set up the database, 
install dependencies, and run the Python Flask application.

------------------------------------------------------------------------------
PREREQUISITES
------------------------------------------------------------------------------
1. Python (3.8 or newer)
2. MySQL Server (Running on localhost)
3. MySQL Workbench (Recommended for running the SQL script)

------------------------------------------------------------------------------
STEP 1: DATABASE SETUP
------------------------------------------------------------------------------
You must create the database structure before running the app.

1. Open MySQL Workbench.
2. Connect to your local database instance.
3. Open a new SQL tab (File > New Query Tab).
4. Copy and paste the entire SQL block found at the bottom of this file 
   (under "APPENDIX: DATABASE SCHEMA SCRIPT").
5. Execute the script (Click the lightning bolt icon ⚡).
   - This will create the database `peer_support_db` and populate it with 
     demo users (Admin, Counselor, Ashley, etc.).

------------------------------------------------------------------------------
STEP 2: INSTALL PYTHON LIBRARIES
------------------------------------------------------------------------------
Open your terminal (Mac/Linux) or Command Prompt (Windows) and navigate to 
the project folder. Run:

    pip install flask mysql-connector-python

------------------------------------------------------------------------------
STEP 3: CONFIGURE DATABASE CONNECTION
------------------------------------------------------------------------------
1. Open your `app.py` file in your code editor.
2. Locate the `db_config` dictionary (approx. lines 15-20).
3. Update the 'password' value to match YOUR MySQL root password.

   db_config = {
       'host': 'localhost',
       'user': 'root',
       'password': 'YOUR_MYSQL_PASSWORD_HERE',  <-- CHANGE THIS
       'database': 'peer_support_db'
   }

------------------------------------------------------------------------------
STEP 4: RUN THE APPLICATION
------------------------------------------------------------------------------
1. In your terminal, verify you are in the project folder.
2. Run the command:

    python app.py

3. If successful, you will see:
   * Running on http://127.0.0.1:5000

------------------------------------------------------------------------------
STEP 5: LOGGING IN (DEMO ACCOUNTS)
------------------------------------------------------------------------------
Open your browser to http://127.0.0.1:5000.
Use these credentials (Password is '123' for all):

| Role      | Username | Password | Notes                          |
|-----------|----------|----------|--------------------------------|
| Admin     | admin    | 123      | Access scoring & moderation    |
| Moderator | mod      | 123      | Review reports & flag users    |
| Counselor | counselor| 123      | View caseload & assign plans   |
| Student   | ashley   | 123      | Regular student (Score: 100)   |
| Student   | john     | 123      | Regular student (Score: 100)   |
| Student   | help     | 123      | Troubled student (Score: 50)   |

==============================================================================
APPENDIX: DATABASE SCHEMA SCRIPT
(Copy and Run this in MySQL Workbench)
==============================================================================

-- 1. Create Database
DROP DATABASE IF EXISTS peer_support_db;
CREATE DATABASE IF NOT EXISTS peer_support_db;
USE peer_support_db;

-- 2. Base Account Table
CREATE TABLE Account (
    account_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    password VARCHAR(255) NOT NULL, 
    role ENUM('admin', 'moderator', 'counselor', 'student') NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 3. Role-Specific Tables
CREATE TABLE Admin (
    admin_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    full_name VARCHAR(100),
    FOREIGN KEY (account_id) REFERENCES Account(account_id) ON DELETE CASCADE
);

CREATE TABLE Moderator (
    moderator_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    full_name VARCHAR(100),
    FOREIGN KEY (account_id) REFERENCES Account(account_id) ON DELETE CASCADE
);

CREATE TABLE Counselor (
    counselor_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    full_name VARCHAR(100),
    specialization VARCHAR(100),
    FOREIGN KEY (account_id) REFERENCES Account(account_id) ON DELETE CASCADE
);

CREATE TABLE Student (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    full_name VARCHAR(100),
    program VARCHAR(100),
    points INT DEFAULT 0,
    score_percentage FLOAT DEFAULT 100.0,
    bio TEXT,
    interests TEXT,
    violations INT DEFAULT 0,
    FOREIGN KEY (account_id) REFERENCES Account(account_id) ON DELETE CASCADE
);

-- 4. Feature Tables

-- Mood Tracking
CREATE TABLE MoodCheckIn (
    checkin_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    mood_level INT NOT NULL,
    severity_level VARCHAR(20),
    note TEXT,
    checkin_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES Student(student_id)
);

-- Posts & Content
CREATE TABLE Post (
    post_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    content TEXT NOT NULL,
    image_url VARCHAR(255),
    is_anonymous BOOLEAN DEFAULT FALSE,
    likes INT DEFAULT 0,
    is_retweet BOOLEAN DEFAULT FALSE,
    retweet_of VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES Student(student_id)
);

CREATE TABLE Comment (
    comment_id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL,
    student_id INT NOT NULL,
    content TEXT NOT NULL,
    is_anonymous BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES Post(post_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES Student(student_id)
);

-- Connections
CREATE TABLE Friendship (
    friendship_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id_1 INT NOT NULL,
    student_id_2 INT NOT NULL,
    status ENUM('Pending', 'Accepted') DEFAULT 'Pending',
    FOREIGN KEY (student_id_1) REFERENCES Student(student_id),
    FOREIGN KEY (student_id_2) REFERENCES Student(student_id)
);

CREATE TABLE PrivateChat (
    chat_id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT NOT NULL,
    receiver_id INT NOT NULL,
    message TEXT NOT NULL,
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Counselor Features
CREATE TABLE Assignment (
    assignment_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    counselor_id INT NOT NULL,
    status VARCHAR(50) DEFAULT 'Pending',
    FOREIGN KEY (student_id) REFERENCES Student(student_id),
    FOREIGN KEY (counselor_id) REFERENCES Counselor(counselor_id)
);

CREATE TABLE CounselorAppointment (
    appointment_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    counselor_id INT NOT NULL,
    appointment_date DATETIME NOT NULL,
    duration INT DEFAULT 60,
    reason TEXT,
    notes TEXT,
    status VARCHAR(50) DEFAULT 'Pending',
    FOREIGN KEY (student_id) REFERENCES Student(student_id),
    FOREIGN KEY (counselor_id) REFERENCES Counselor(counselor_id)
);

CREATE TABLE TherapeuticActionPlan (
    plan_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    title VARCHAR(200),
    goals TEXT,
    strategies TEXT,
    timeline VARCHAR(100),
    status VARCHAR(50) DEFAULT 'Active',
    FOREIGN KEY (student_id) REFERENCES Student(student_id)
);

-- Moderation
CREATE TABLE Report (
    report_id INT AUTO_INCREMENT PRIMARY KEY,
    reporter_id INT NOT NULL,
    target_type ENUM('post', 'comment', 'user'),
    target_id INT NOT NULL,
    reason TEXT,
    status VARCHAR(50) DEFAULT 'Pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE FlagAccount (
    flag_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    moderator_id INT NOT NULL,
    reason TEXT,
    status VARCHAR(50) DEFAULT 'Pending',
    FOREIGN KEY (student_id) REFERENCES Student(student_id),
    FOREIGN KEY (moderator_id) REFERENCES Moderator(moderator_id)
);

CREATE TABLE Appeal (
    appeal_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    reason TEXT,
    status VARCHAR(50) DEFAULT 'Pending',
    FOREIGN KEY (student_id) REFERENCES Student(student_id)
);

CREATE TABLE Announcement (
    announcement_id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200),
    content TEXT,
    date DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Notification (
    notif_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    message TEXT,
    link VARCHAR(255),
    is_read BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- SEED DATA
-- 1. Admin (admin/123)
INSERT INTO Account (username, password, role) VALUES ('admin', '123', 'admin');
INSERT INTO Admin (account_id, full_name) VALUES (LAST_INSERT_ID(), 'Fatin Admin');

-- 2. Moderator (mod/123)
INSERT INTO Account (username, password, role) VALUES ('mod', '123', 'moderator');
INSERT INTO Moderator (account_id, full_name) VALUES (LAST_INSERT_ID(), 'Rayyan Moderator');

-- 3. Counselor (counselor/123)
INSERT INTO Account (username, password, role) VALUES ('counselor', '123', 'counselor');
INSERT INTO Counselor (account_id, full_name, specialization) VALUES (LAST_INSERT_ID(), 'Siti Counselor', 'Anxiety & Stress');

-- 4. Students
-- Ashley (ashley/123)
INSERT INTO Account (username, password, role) VALUES ('ashley', '123', 'student');
INSERT INTO Student (account_id, full_name, program, points, bio, interests) 
VALUES (LAST_INSERT_ID(), 'Ashley Law', 'Computer Science', 85, 'CS Student loves AI.', 'coding,music,gaming');

-- John (john/123)
INSERT INTO Account (username, password, role) VALUES ('john', '123', 'student');
INSERT INTO Student (account_id, full_name, program, points, bio, interests) 
VALUES (LAST_INSERT_ID(), 'John Peer', 'IT', 120, 'Tech enthusiast.', 'gaming,coding');

-- Troubled Student (help/123)
INSERT INTO Account (username, password, role) VALUES ('help', '123', 'student');
INSERT INTO Student (account_id, full_name, program, points, score_percentage, bio, violations) 
VALUES (LAST_INSERT_ID(), 'Troubled Student', 'Arts', 10, 50.0, 'Need help.', 2);