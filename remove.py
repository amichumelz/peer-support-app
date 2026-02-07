import mysql.connector

# STOP: You must copy these credentials from your Aiven Console 'Overview' tab
db_config = {
    'host': 'peer-support-system-fatinshamirah212-93b4.j.aivencloud.com', # Change this!
    'user': 'avnadmin',                                                        # Change this!
    'password': 'AVNS_qclUfTKSrqQyzmN9pz4',                                  # Change this!
    'database': 'defaultdb',
    'port': 26591                                                              # Aiven port is usually NOT 3306
}

def remove_aaa_from_cloud():
    try:
        # Aiven requires ssl_disabled=False or specific SSL certificates
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Target IDs for 'aaa'
        ACC_ID = 17
        STU_ID = 8

        print(f"🔗 Connected to LIVE Aiven DB. Wiping Account {ACC_ID}...")

        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")

        # Comprehensive list of tables where student_id 8 or account_id 17 exists
        queries = [
            ("DELETE FROM ScoreTransaction WHERE student_id = %s", (STU_ID,)),
            ("DELETE FROM Friendship WHERE student_id_1 = %s OR student_id_2 = %s", (STU_ID, STU_ID)),
            ("DELETE FROM MoodCheckIn WHERE student_id = %s", (STU_ID,)),
            ("DELETE FROM CounselorAppointment WHERE student_id = %s", (STU_ID,)),
            ("DELETE FROM Assignment WHERE student_id = %s", (STU_ID,)),
            ("DELETE FROM TherapeuticActionPlan WHERE student_id = %s", (STU_ID,)),
            ("DELETE FROM PrivateChat WHERE sender_id = %s OR receiver_id = %s", (ACC_ID, ACC_ID)),
            ("DELETE FROM Notification WHERE user_id = %s", (ACC_ID,)),
            ("DELETE FROM LoginSession WHERE account_id = %s", (ACC_ID,)),
            ("DELETE FROM LogoutSession WHERE account_id = %s", (ACC_ID,)),
            ("DELETE FROM Post WHERE student_id = %s", (STU_ID,)),
            ("DELETE FROM Student WHERE student_id = %s", (STU_ID,)),
            ("DELETE FROM Account WHERE account_id = %s", (ACC_ID,))
        ]

        for query, val in queries:
            cursor.execute(query, val)
            print(f"🗑 {cursor.rowcount} rows removed from {query.split()[2]}")

        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
        
        # THE MOST IMPORTANT PART
        conn.commit()
        print("\n✨ LIVE DATABASE UPDATED. 'aaa' is gone.")

    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        print("TIP: Make sure your IP address is allowed in the Aiven 'Allowed IPs' section!")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    remove_aaa_from_cloud()