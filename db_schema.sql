-- ==============================================================================
-- DATABASE SCHEMA: DIGITAL PEER SUPPORT SYSTEM
-- TOTAL TABLES: 31
-- ==============================================================================

DROP DATABASE IF EXISTS peer_support_db;
CREATE DATABASE IF NOT EXISTS peer_support_db;
USE peer_support_db;

-- ------------------------------------------------------------------------------
-- GROUP A: CORE IDENTITY & ACCESS
-- ------------------------------------------------------------------------------

-- 1. Base credentials for all system actors
CREATE TABLE Account (
    account_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    password VARCHAR(255) NOT NULL, 
    role ENUM('admin', 'moderator', 'counselor', 'student') NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 2. System Administrator profiles
CREATE TABLE Admin (
    admin_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    full_name VARCHAR(100),
    FOREIGN KEY (account_id) REFERENCES Account(account_id) ON DELETE CASCADE
);

-- 3. Community Moderator profiles
CREATE TABLE Moderator (
    moderator_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    full_name VARCHAR(100),
    FOREIGN KEY (account_id) REFERENCES Account(account_id) ON DELETE CASCADE
);

-- 4. Professional Counselor profiles
CREATE TABLE Counselor (
    counselor_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    full_name VARCHAR(100),
    specialization VARCHAR(100),
    FOREIGN KEY (account_id) REFERENCES Account(account_id) ON DELETE CASCADE
);

-- 5. Primary Student profiles with Wellness scoring
CREATE TABLE Student (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    full_name VARCHAR(100),
    program VARCHAR(100),
    points INT DEFAULT 100,
    score_percentage FLOAT DEFAULT 100.0,
    bio TEXT,
    interests TEXT,
    violations INT DEFAULT 0,
    avatar_url VARCHAR(255),
    FOREIGN KEY (account_id) REFERENCES Account(account_id) ON DELETE CASCADE
);

-- 6. Extended student biography and interests
CREATE TABLE Profile (
    profile_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    interests TEXT,
    introduction TEXT,
    program VARCHAR(100),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE
);

-- ------------------------------------------------------------------------------
-- GROUP B: SESSIONS & SECURITY
-- ------------------------------------------------------------------------------

-- 7. Audit log for user logins
CREATE TABLE LoginSession (
    session_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    login_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (account_id) REFERENCES Account(account_id) ON DELETE CASCADE
);

-- 8. Audit log for user logouts
CREATE TABLE LogoutSession (
    logout_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    logout_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES Account(account_id) ON DELETE CASCADE
);

-- 9. OTP management for password recovery
CREATE TABLE PasswordReset (
    reset_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    otp_code VARCHAR(10),
    requested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME,
    is_used BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE
);

-- 10. Persistent record of account suspensions
CREATE TABLE Suspension (
    suspension_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    admin_id INT NOT NULL,
    duration VARCHAR(50),
    reason VARCHAR(100),
    start_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES Admin(admin_id)
);

-- 11. Tracking temporary posting restrictions
CREATE TABLE RestrictionPeriod (
    restriction_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    start_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    end_date DATETIME,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE
);

-- ------------------------------------------------------------------------------
-- GROUP C: COMMUNITY & CONTENT
-- ------------------------------------------------------------------------------

-- 12. Main forum content
CREATE TABLE Post (
    post_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    content TEXT NOT NULL,
    image_url TEXT, 
    is_anonymous BOOLEAN DEFAULT FALSE,
    likes INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE
);

-- 13. Responses to posts
CREATE TABLE Comment (
    comment_id INT AUTO_INCREMENT PRIMARY KEY,
    post_id INT NOT NULL,
    student_id INT NOT NULL,
    content TEXT NOT NULL,
    is_anonymous BOOLEAN DEFAULT FALSE,
    likes INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES Post(post_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE
);

-- 14. Engagement tracking for gamification
CREATE TABLE `Like` (
    like_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    post_id INT DEFAULT NULL,
    comment_id INT DEFAULT NULL,
    liked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES Post(post_id) ON DELETE CASCADE,
    FOREIGN KEY (comment_id) REFERENCES Comment(comment_id) ON DELETE CASCADE
);

-- 15. Moderator audit for removed posts
CREATE TABLE PostDeletion (
    deletion_id INT AUTO_INCREMENT PRIMARY KEY,
    moderator_id INT NOT NULL,
    post_id INT,
    reason VARCHAR(255),
    deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (moderator_id) REFERENCES Moderator(moderator_id)
);

-- 16. Moderator audit for removed comments
CREATE TABLE CommentDeletion (
    deletion_id INT AUTO_INCREMENT PRIMARY KEY,
    moderator_id INT NOT NULL,
    comment_id INT,
    reason VARCHAR(255),
    deleted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (moderator_id) REFERENCES Moderator(moderator_id)
);

-- 17. Official system announcements
CREATE TABLE Announcement (
    announcement_id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(200),
    content TEXT,
    date DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------------------------
-- GROUP D: WELLNESS & CLINICAL LOGIC
-- ------------------------------------------------------------------------------

-- 18. Daily student self-assessment logs
CREATE TABLE MoodCheckIn (
    checkin_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    mood_level INT NOT NULL, 
    severity_level VARCHAR(20),
    note TEXT,
    checkin_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE
);

-- 19. System alerts for critical wellness drops
CREATE TABLE MoodAlert (
    alert_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    admin_id INT,
    weekly_avg_mood FLOAT,
    severity_level VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (admin_id) REFERENCES Admin(admin_id)
);

-- 20. Structured goals and strategies from counselors
CREATE TABLE TherapeuticActionPlan (
    plan_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    title VARCHAR(200),
    goals TEXT,
    strategies TEXT,
    timeline VARCHAR(100),
    status VARCHAR(50) DEFAULT 'Active',
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE
);

-- 21. Scheduled counseling session records
CREATE TABLE CounselorAppointment (
    appointment_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    counselor_id INT NOT NULL,
    appointment_date DATETIME NOT NULL,
    duration INT DEFAULT 60,
    reason TEXT,
    notes TEXT,
    status VARCHAR(50) DEFAULT 'Pending',
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (counselor_id) REFERENCES Counselor(counselor_id) ON DELETE CASCADE
);

-- ------------------------------------------------------------------------------
-- GROUP E: SOCIAL & COMMUNICATION
-- ------------------------------------------------------------------------------

-- 22. Peer connection status
CREATE TABLE Friendship (
    friendship_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id_1 INT NOT NULL,
    student_id_2 INT NOT NULL,
    status ENUM('Pending', 'Accepted', 'Declined') DEFAULT 'Pending',
    FOREIGN KEY (student_id_1) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id_2) REFERENCES Student(student_id) ON DELETE CASCADE
);

-- 23. Direct message history
CREATE TABLE PrivateChat (
    chat_id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT NOT NULL, 
    receiver_id INT NOT NULL,
    message TEXT NOT NULL,
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES Account(account_id) ON DELETE CASCADE,
    FOREIGN KEY (receiver_id) REFERENCES Account(account_id) ON DELETE CASCADE
);

-- 24. Algorithm-based suggestion logs
CREATE TABLE PeerMatch (
    match_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id_1 INT NOT NULL,
    student_id_2 INT NOT NULL,
    compatibility_score FLOAT,
    status VARCHAR(50),
    FOREIGN KEY (student_id_1) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (student_id_2) REFERENCES Student(student_id) ON DELETE CASCADE
);

-- ------------------------------------------------------------------------------
-- GROUP F: MODERATION & DISCIPLINARY
-- ------------------------------------------------------------------------------

-- 25. User-initiated content complaints
CREATE TABLE Report (
    report_id INT AUTO_INCREMENT PRIMARY KEY,
    reporter_id INT NOT NULL,
    target_type ENUM('post', 'comment'),
    target_id INT NOT NULL,
    reason VARCHAR(100),
    status ENUM('Pending', 'Resolved', 'Dismissed', 'Escalated') DEFAULT 'Pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reporter_id) REFERENCES Account(account_id) ON DELETE CASCADE
);

-- 26. Moderator flags for behavioral monitoring
CREATE TABLE FlagAccount (
    flag_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    moderator_id INT NOT NULL,
    reason TEXT,
    status ENUM('Pending', 'Dismissed', 'Suspended') DEFAULT 'Pending',
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (moderator_id) REFERENCES Moderator(moderator_id) ON DELETE CASCADE
);

-- 27. Student requests for restriction reversal
CREATE TABLE Appeal (
    appeal_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    reason TEXT,
    status ENUM('Pending', 'Approved', 'Denied') DEFAULT 'Pending',
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE
);

-- ------------------------------------------------------------------------------
-- GROUP G: SYSTEM LOGS & UTILITIES
-- ------------------------------------------------------------------------------

-- 28. Audit trail for gamification point changes
CREATE TABLE ScoreTransaction (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    action_type VARCHAR(50), 
    points_change INT,
    resulting_score INT,
    transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE
);

-- 29. Real-time push alerts for all users
CREATE TABLE Notification (
    notif_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL, 
    message TEXT,
    link VARCHAR(255),
    is_read BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Account(account_id) ON DELETE CASCADE
);

-- 30. Administrative mapping of students to counselors
CREATE TABLE Assignment (
    assignment_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    counselor_id INT NOT NULL,
    status ENUM('Pending', 'Accepted', 'Declined') DEFAULT 'Pending',
    FOREIGN KEY (student_id) REFERENCES Student(student_id) ON DELETE CASCADE,
    FOREIGN KEY (counselor_id) REFERENCES Counselor(counselor_id) ON DELETE CASCADE
);

-- 31. Tracking of counselor-generated CSV reports
CREATE TABLE ExportData (
    export_id INT AUTO_INCREMENT PRIMARY KEY,
    counselor_id INT NOT NULL,
    export_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    file_path VARCHAR(255),
    FOREIGN KEY (counselor_id) REFERENCES Counselor(counselor_id) ON DELETE CASCADE
);

-- ==============================================================================
-- SEED DATA (PRODUCTION ALIGNED)
-- ==============================================================================

INSERT INTO Account (account_id, username, password, role) VALUES 
(1, 'admin', '123', 'admin'),
(2, 'mod', '123', 'moderator'),
(3, 'counselor', '123', 'counselor'),
(4, 'ashley', '123', 'student'),
(5, 'john', '123', 'student'),
(6, 'help', '123', 'student');

INSERT INTO Admin (admin_id, account_id, full_name) VALUES (1, 1, 'Fatin Admin');
INSERT INTO Moderator (moderator_id, account_id, full_name) VALUES (1, 2, 'Rayyan Moderator');
INSERT INTO Counselor (counselor_id, account_id, full_name, specialization) VALUES (1, 3, 'Siti Counselor', 'Anxiety & Stress');

INSERT INTO Student (student_id, account_id, full_name, program, points, score_percentage, bio, interests, avatar_url) VALUES 
(1, 4, 'Ashley Law', 'Computer Science', 90, 75.0, 'CS Student loves AI.', 'coding,music,gaming,chess', 'https://api.dicebear.com/7.x/avataaars/svg?seed=Zoe'),
(2, 5, 'John Peer', 'IT', 50, 60.0, 'Tech enthusiast.', 'gaming,coding', NULL),
(3, 6, 'Troubled Student', 'Arts', 10, 50.0, 'Need help.', NULL, NULL);

INSERT INTO TherapeuticActionPlan (plan_id, student_id, title, status) VALUES 
(1, 4, 'Anxiety Management Protocol', 'Active'),
(2, 1, 'Academic Recovery Plan', 'Completed');