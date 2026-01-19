import mysql.connector
from mysql.connector import Error

# UPDATE YOUR DB PASSWORD HERE
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '211521', 
    'database': 'peer_support_db'
}

# These are the Tables and Columns your simpan.py RELIES on.
# Format: 'TableName': ['col1', 'col2']
required_schema = {
    'Account': ['account_id', 'username', 'password', 'role', 'is_active'],
    'Student': ['student_id', 'account_id', 'full_name', 'program', 'points', 'score_percentage', 'bio', 'interests', 'violations'],
    'Admin': ['admin_id', 'account_id', 'full_name'],
    'Moderator': ['moderator_id', 'account_id', 'full_name'],
    'Counselor': ['counselor_id', 'account_id', 'full_name', 'specialization'],
    'LoginSession': ['session_id', 'account_id', 'login_time'],
    'LogoutSession': ['logout_id', 'account_id'],
    'Post': ['post_id', 'student_id', 'content', 'image_url', 'is_anonymous', 'created_at'],
    'Comment': ['comment_id', 'post_id', 'student_id', 'content'],
    'Like': ['like_id', 'student_id', 'post_id'],  # Note: "Like" is a reserved word, usually requires backticks in SQL
    'MoodCheckIn': ['checkin_id', 'student_id', 'mood_level', 'severity_level', 'note'],
    'MoodAlert': ['alert_id', 'student_id', 'weekly_avg_mood', 'assignment_status'],
    'TherapeuticActionPlan': ['plan_id', 'student_id', 'title', 'goals', 'status'],
    'Assignment': ['assignment_id', 'student_id', 'counselor_id', 'status'],
    'CounselorAppointment': ['appointment_id', 'student_id', 'counselor_id', 'appointment_date', 'status'],
    'Notification': ['notif_id', 'user_id', 'message'],
    'Friendship': ['friendship_id', 'student_id_1', 'student_id_2', 'status'],
    'PeerMatch': ['match_id', 'student_id_1', 'student_id_2', 'status'],
    'PrivateChat': ['chat_id', 'sender_id', 'receiver_id', 'message'],
    'ScoreTransaction': ['transaction_id', 'student_id', 'points_change', 'resulting_score'],
    'Report': ['report_id', 'target_id', 'target_type', 'reason', 'status'],
    'FlagAccount': ['flag_id', 'student_id', 'moderator_id', 'status'],
    'Suspension': ['suspension_id', 'student_id', 'start_date', 'reason'],
    'Announcement': ['announcement_id', 'title', 'content', 'date']
}

def check_structure():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        print("--- DATABASE INTEGRITY CHECK ---")
        
        all_good = True
        
        for table, required_columns in required_schema.items():
            # 1. Check if Table Exists
            try:
                # Handle reserved word `Like` by adding backticks for the check if necessary, 
                # but SHOW COLUMNS usually works with the string name.
                cursor.execute(f"SHOW COLUMNS FROM `{table}`")
                columns = [row[0] for row in cursor.fetchall()]
                print(f"✅ Table '{table}' exists.")
                
                # 2. Check if Columns Exist
                for col in required_columns:
                    if col not in columns:
                        print(f"   ❌ MISSING COLUMN: '{col}' in table '{table}'")
                        all_good = False
            
            except Error as err:
                if err.errno == 1146:
                    print(f"❌ MISSING TABLE: '{table}'")
                    all_good = False
                else:
                    print(f"⚠️ Error checking '{table}': {err}")

        print("\n--------------------------------")
        if all_good:
            print("🎉 SUCCESS: Your Database Structure matches the Code!")
        else:
            print("⛔ FAILURE: You are missing tables or columns (see above).")
            print("👉 Fix: Open db_schema.sql, find the missing CREATE TABLE code, and run it in MySQL.")
            
        conn.close()
    except Error as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    check_structure()