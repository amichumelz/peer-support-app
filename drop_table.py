import mysql.connector
import os

# Your Aiven Database Configuration
db_config = {
    'host': os.environ.get('DB_HOST', 'peer-support-system-fatinshamirah212-93b4.j.aivencloud.com'),
    'user': os.environ.get('DB_USER', 'avnadmin'),
    'password': os.environ.get('DB_PASSWORD', 'AVNS_qclUfTKSrqQyzmN9pz4'),
    'database': os.environ.get('DB_NAME', 'defaultdb'),
    'port': int(os.environ.get('DB_PORT', 26591)),
    'ssl_disabled': False
}

def drop_checkin_table():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # THE COMMAND TO DELETE THE TABLE
        cursor.execute("DROP TABLE IF EXISTS CheckInMessage")
        
        print("✅ Success: Table 'CheckInMessage' has been dropped (deleted).")
        
        conn.commit()
        conn.close()

    except mysql.connector.Error as err:
        print(f"❌ Error: {err}")

if __name__ == "__main__":
    drop_checkin_table()