import mysql.connector
import os

# ==========================================
# DATABASE CONFIGURATION
# ==========================================
db_config = {
    'host': 'peer-support-system-fatinshamirah212-93b4.j.aivencloud.com',
    'user': 'avnadmin',
    'password': 'AVNS_qclUfTKSrqQyzmN9pz4',
    'database': 'defaultdb',
    'port': 26591,
    'ssl_disabled': False
}

def remove_duplicates():
    try:
        print("🔌 Connecting to Database...")
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # ---------------------------------------------------------
        # 1. CLEAN FRIENDSHIP TABLE
        # Logic: Delete rows where student_1 and student_2 are the same, 
        # but keep the one with the smallest ID (the first one).
        # ---------------------------------------------------------
        print("🧹 Cleaning Friendship table...")
        sql_friend = """
        DELETE t1 FROM Friendship t1
        INNER JOIN Friendship t2 
        WHERE t1.friendship_id > t2.friendship_id 
          AND t1.student_id_1 = t2.student_id_1 
          AND t1.student_id_2 = t2.student_id_2;
        """
        cursor.execute(sql_friend)
        print(f"   - Removed {cursor.rowcount} duplicate friendships.")

        # ---------------------------------------------------------
        # 2. CLEAN PRIVATE CHAT (Double Sends)
        # Logic: Delete messages that are identical (sender, receiver, content)
        # and sent within 5 seconds of the previous one.
        # ---------------------------------------------------------
        print("🧹 Cleaning PrivateChat table (Double sends)...")
        sql_chat = """
        DELETE t1 FROM PrivateChat t1
        INNER JOIN PrivateChat t2 
        ON t1.sender_id = t2.sender_id 
           AND t1.receiver_id = t2.receiver_id 
           AND t1.message = t2.message
           AND t1.chat_id > t2.chat_id
        WHERE TIMESTAMPDIFF(SECOND, t2.sent_at, t1.sent_at) < 5;
        """
        cursor.execute(sql_chat)
        print(f"   - Removed {cursor.rowcount} duplicate messages.")

        # ---------------------------------------------------------
        # 3. CLEAN SCORE TRANSACTIONS (Spam/Double Clicks)
        # Logic: Delete 'Liked a Post' entries for the same student
        # that happened within 2 seconds of each other.
        # ---------------------------------------------------------
        print("🧹 Cleaning ScoreTransaction table (Spam clicks)...")
        sql_score = """
        DELETE t1 FROM ScoreTransaction t1
        INNER JOIN ScoreTransaction t2 
        ON t1.student_id = t2.student_id 
           AND t1.action_type = t2.action_type
           AND t1.transaction_id > t2.transaction_id
        WHERE t1.action_type = 'Liked a Post'
          AND TIMESTAMPDIFF(SECOND, t2.transaction_date, t1.transaction_date) < 2;
        """
        cursor.execute(sql_score)
        print(f"   - Removed {cursor.rowcount} spam score entries.")

        conn.commit()
        print("\n✅ Database cleanup complete!")

    except mysql.connector.Error as err:
        print(f"❌ Error: {err}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()

if __name__ == "__main__":
    remove_duplicates()