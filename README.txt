==============================================================================
USER GUIDE: DIGITAL PEER SUPPORT SYSTEM (v2.0)
==============================================================================

This document contains step-by-step instructions to set up the environment, 
configure cloud integrations, and run the Python Flask application.

------------------------------------------------------------------------------
PREREQUISITES
------------------------------------------------------------------------------
1. Python (3.10 or newer)
2. MySQL Server (Localhost or Aiven Cloud instance)
3. Cloudinary Account (For forum media storage)
4. Google App Password (For SMTP email/OTP delivery)

------------------------------------------------------------------------------
STEP 0: ACCESS LIVE SYSTEM (RENDERED)
------------------------------------------------------------------------------
You can access the fully functional, live version of the system here:

Live URL: https://peer-support-app.onrender.com

------------------------------------------------------------------------------
STEP 1: DATABASE SETUP
------------------------------------------------------------------------------
You must initialize the 31-table schema before running the app locally.

1. Open MySQL Workbench and connect to your instance.
2. Open a new SQL tab.
3. Copy the entire script from 'db_schema.sql' and execute it.
   - This creates 'peer_support_db' with all relational constraints.
   - It populates the system with necessary Seed Data for all roles.

------------------------------------------------------------------------------
STEP 2: INSTALL PYTHON LIBRARIES
------------------------------------------------------------------------------
Open your terminal in the project folder and run the following command to 
install all required dependencies:

    pip install -r requirements.txt

------------------------------------------------------------------------------
STEP 3: CONFIGURATION
------------------------------------------------------------------------------
Open 'app.py' and ensure the following configurations are updated:

1. DATABASE: Update 'db_config' with your MySQL credentials.
2. CLOUDINARY: Input your cloud_name, api_key, and api_secret.
3. EMAIL: Update SENDER_EMAIL and SENDER_PASSWORD (App Pass).

------------------------------------------------------------------------------
STEP 4: RUN THE APPLICATION
------------------------------------------------------------------------------
1. In your terminal, run:

    python app.py

2. Access the system at: http://127.0.0.1:5000

------------------------------------------------------------------------------
STEP 5: DEMO ACCOUNTS (Password: '123' for all)
------------------------------------------------------------------------------
| Role      | Username | Key Features                               |
|-----------|----------|--------------------------------------------|
| Admin     | admin    | Mood Alerts, Counselor Assign, Appeals     |
| Moderator | mod      | Review Reports, Flag Users, Announcements  |
| Counselor | counselor| Manage Caseload, Action Plans, Session Note|
| Student   | ashley   | Forum Posting, Mood Logs, Peer Matching    |

==============================================================================
SYSTEM LOGS & VERIFICATION
==============================================================================
To verify your cloud database implementation, you can run the audit script:

    python check_data.py

This will display a summary of all 31 tables and their current data.
==============================================================================