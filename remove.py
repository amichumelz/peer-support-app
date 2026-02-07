import mysql.connector

db_config = {
    'host': 'peer-support-system-fatinshamirah212-93b4.j.aivencloud.com',
    'user': 'avnadmin',
    'password': 'AVNS_qclUfTKSrqQyzmN9pz4',
    'database': 'defaultdb',
    'port': 26591
}

def force_fix_siti_load():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        SITI_ID = 1 

        print(f"🔗 Checking Assignment table for Counselor {SITI_ID}...")

        # This removes the most recent accepted assignment for Siti
        query = """
            DELETE FROM Assignment 
            WHERE counselor_id = %s 
            AND status = 'Accepted' 
            ORDER BY assignment_id DESC 
            LIMIT 1
        """
        cursor.execute(query, (SITI_ID,))
        conn.commit()
        
        print(f"🗑 Removed {cursor.rowcount} row(s).")
        print("✨ Refresh your dashboard now. It should show 5/5.")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

force_fix_siti_load()