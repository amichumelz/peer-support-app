import mysql.connector

db_config = {
    'host': 'peer-support-system-fatinshamirah212-93b4.j.aivencloud.com',
    'user': 'avnadmin',
    'password': 'AVNS_qclUfTKSrqQyzmN9pz4',
    'database': 'defaultdb',
    'port': 26591
}

def drop_one_siti_appointment():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # ID Siti Counselor adalah 1
        SITI_ID = 1 

        print(f"🔗 Connected to Aiven. Dropping latest appointment for Siti (ID {SITI_ID})...")

        # Query untuk membuang temu janji paling baru (ID terbesar) bagi Siti
        query = """
            DELETE FROM CounselorAppointment 
            WHERE counselor_id = %s 
            ORDER BY appointment_id DESC 
            LIMIT 1
        """

        cursor.execute(query, (SITI_ID,))
        
        if cursor.rowcount > 0:
            conn.commit()
            print(f"🗑 Berjaya membuang {cursor.rowcount} rekod temu janji.")
            print("✨ Sekarang Siti patut ada 5 kes sahaja (jika tadi ada 6). Sila refresh dashboard!")
        else:
            print("⚠️ Tiada temu janji dijumpai untuk Siti Counselor.")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    drop_one_siti_appointment()