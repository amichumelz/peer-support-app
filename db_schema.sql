-- 1. Create Database
DROP DATABASE IF EXISTS peer_support_db;
CREATE DATABASE IF NOT EXISTS peer_support_db;
USE peer_support_db;

-- 2. Base Account Table (Stores Login Credentials)
CREATE TABLE Account (
    account_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    password VARCHAR(255) NOT NULL, -- Storing plain text for demo ('123')
    role ENUM('admin', 'moderator', 'counselor', 'student') NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

UPDATE Account SET username = TRIM(username), password = TRIM(password);

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
    interests TEXT, -- Stored as comma-separated string for simplicity
    violations INT DEFAULT 0,
    FOREIGN KEY (account_id) REFERENCES Account(account_id) ON DELETE CASCADE
);

-- 4. Feature Tables

-- Mood Tracking
CREATE TABLE MoodCheckIn (
    checkin_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    mood_level INT NOT NULL, -- 1 to 5
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
    image_url VARCHAR(1000),
    is_anonymous BOOLEAN DEFAULT FALSE,
    likes INT DEFAULT 0,
    is_retweet BOOLEAN DEFAULT FALSE,
    retweet_of VARCHAR(100), -- Original author name
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
ALTER TABLE Comment ADD COLUMN likes INT DEFAULT 0;

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
    sender_id INT NOT NULL, -- References Account ID for universal chat
    receiver_id INT NOT NULL,
    message TEXT NOT NULL,
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Counselor Features
CREATE TABLE Assignment (
    assignment_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    counselor_id INT NOT NULL,
    status VARCHAR(50) DEFAULT 'Pending', -- Pending, Accepted, Info Requested
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
    reporter_id INT NOT NULL, -- Account ID
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
    user_id INT NOT NULL, -- Account ID
    message TEXT,
    link VARCHAR(255),
    is_read BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ==========================================
-- 5. ADDITIONAL FEATURE TABLES (From Specification)
-- ==========================================

-- 5.1 Authentication & Sessions
CREATE TABLE LoginSession (
    session_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    login_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (account_id) REFERENCES Account(account_id) ON DELETE CASCADE
);

CREATE TABLE LogoutSession (
    logout_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    logout_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES Account(account_id) ON DELETE CASCADE
);

CREATE TABLE PasswordReset (
    reset_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    otp_code VARCHAR(10),
    requested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    new_pass VARCHAR(255),
    is_used BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE
);

-- 5.2 Extended Student Profiles
-- (Optional: Use if you want to separate details from the main Student table)
CREATE TABLE Profile (
    profile_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    interests TEXT,
    introduction TEXT,
    program VARCHAR(100),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE
);

-- 5.3 Engagement & Gamification
CREATE TABLE `Like` (
    like_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    post_id INT,
    comment_id INT,
    liked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES Post(post_id) ON DELETE CASCADE,
    FOREIGN KEY (comment_id) REFERENCES Comment(comment_id) ON DELETE CASCADE
);

CREATE TABLE ScoreTransaction (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    action_type VARCHAR(50), -- e.g., "Post", "Helpful Comment"
    points_change INT,
    resulting_score INT,
    transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE
);

-- 5.4 Advanced Moderation & Safety
CREATE TABLE MoodAlert (
    alert_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    admin_id INT, -- Admin reviewing the alert
    weekly_avg_mood FLOAT,
    severity_level VARCHAR(20), -- Low, High, Critical
    weeks_below_threshold INT,
    assignment_status VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    reviewed_at DATETIME,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES Admin(admin_id)
);

CREATE TABLE Suspension (
    suspension_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    admin_id INT NOT NULL,
    duration VARCHAR(50), -- e.g., "7 days"
    reason VARCHAR(100),
    violation_type VARCHAR(100),
    justification TEXT,
    start_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    end_date DATETIME,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES Admin(admin_id)
);

CREATE TABLE RestrictionPeriod (
    restriction_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    start_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    end_date DATETIME,
    violation_count INT,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE
);

CREATE TABLE PostDeletion (
    deletion_id INT AUTO_INCREMENT PRIMARY KEY,
    moderator_id INT NOT NULL,
    post_id INT, -- Keeps ID reference even if actual post is gone, or allow NULL
    reason VARCHAR(255),
    deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (moderator_id) REFERENCES Moderator(moderator_id)
);

CREATE TABLE CommentDeletion (
    deletion_id INT AUTO_INCREMENT PRIMARY KEY,
    moderator_id INT NOT NULL,
    comment_id INT,
    reason VARCHAR(255),
    deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (moderator_id) REFERENCES Moderator(moderator_id)
);

-- 5.5 Counselor Tools
CREATE TABLE CheckInMessage (
    message_id INT AUTO_INCREMENT PRIMARY KEY,
    counselor_id INT NOT NULL,
    student_id INT NOT NULL,
    message_content TEXT,
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (counselor_id) REFERENCES Counselor(counselor_id),
    FOREIGN KEY (student_id) REFERENCES Student(student_id)
);

CREATE TABLE ExportData (
    export_id INT AUTO_INCREMENT PRIMARY KEY,
    counselor_id INT NOT NULL,
    export_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    file_path VARCHAR(255),
    FOREIGN KEY (counselor_id) REFERENCES Counselor(counselor_id)
);

-- 5.6 Social Matching
CREATE TABLE PeerMatch (
    match_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id_1 INT NOT NULL,
    student_id_2 INT NOT NULL,
    compatibility_score FLOAT,
    matched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50), -- e.g., Suggested, Connected
    FOREIGN KEY (student_id_1) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id_2) REFERENCES Student(student_id) ON DELETE CASCADE
);

-- ==========================================
-- SEED DATA (Default Users)
-- ==========================================

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
VALUES (LAST_INSERT_ID(), 'John Peer', 'IT', 100, 'Tech enthusiast.', 'gaming,coding');

-- Troubled Student (help/123)
INSERT INTO Account (username, password, role) VALUES ('help', '123', 'student');
INSERT INTO Student (account_id, full_name, program, points, score_percentage, bio, violations) 
VALUES (LAST_INSERT_ID(), 'Troubled Student', 'Arts', 10, 50.0, 'Need help.', 2);