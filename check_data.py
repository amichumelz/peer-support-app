import mysql.connector
import os

# Your Aiven Database Configuration
db_config = {
    'host': 'peer-support-system-fatinshamirah212-93b4.j.aivencloud.com',
    'user': 'avnadmin',
    'password': 'AVNS_qclUfTKSrqQyzmN9pz4',
    'database': 'defaultdb',
    'port': 26591,
    'ssl_disabled': False
}

def inspect_database():
    try:
        print("🔌 Connecting to Aiven Database...")
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()

        # 1. Get List of All Tables
        cursor.execute("SHOW TABLES")
        tables = [table[0] for table in cursor.fetchall()]

        print(f"✅ Connected! Found {len(tables)} tables.\n")

        # 2. Loop through each table and print its content
        for table_name in tables:
            print(f"========================================")
            print(f" 📂 TABLE: {table_name}")
            print(f"========================================")
            
            # Get columns (Added backticks around table_name)
            try:
                cursor.execute(f"SHOW COLUMNS FROM `{table_name}`")
                columns = [col[0] for col in cursor.fetchall()]
                print(f"Columns: {columns}")
                print("-" * 40)

                # Get data rows (Added backticks around table_name)
                cursor.execute(f"SELECT * FROM `{table_name}`")
                rows = cursor.fetchall()

                if not rows:
                    print("   (Empty Table)")
                else:
                    for row in rows:
                        print(f"   {row}")
            except mysql.connector.Error as table_err:
                print(f"   ⚠️ Could not read table: {table_err}")
            
            print("\n")

    except mysql.connector.Error as err:
        print(f"❌ Connection Error: {err}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            conn.close()
            print("🔌 Connection closed.")

if __name__ == "__main__":
    inspect_database()