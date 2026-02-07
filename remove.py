import mysql.connector

db_config = {
    'host': 'peer-support-system-fatinshamirah212-93b4.j.aivencloud.com',
    'user': 'avnadmin',
    'password': 'AVNS_qclUfTKSrqQyzmN9pz4',
    'database': 'defaultdb',
    'port': 26591
}

def fix_accepted_overload():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # Targeting Siti Counselor (ID 1)
        SITI_ID = 1 

        print(f"🔗 Connected to Aiven. Removing one 'Accepted' case for Counselor ID {SITI_ID}...")

        # We remove the latest Accepted assignment to reduce the count from 6 to 5
        query = """
            DELETE FROM Assignment 
            WHERE counselor_id = %s 
            AND status = 'Accepted' 
            ORDER BY assignment_id DESC 
            LIMIT 1
        """

        cursor.execute(query, (SITI_ID,))
        
        if cursor.rowcount > 0:
            conn.commit()
            print(f"🗑 Successfully removed {cursor.rowcount} accepted case.")
            print("✨ Siti Counselor's caseload should now be 5/5. Refresh your dashboard!")
        else:
            print("⚠️ No accepted assignments found for this Counselor ID.")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    fix_accepted_overload()