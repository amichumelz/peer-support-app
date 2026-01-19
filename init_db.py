import mysql.connector

# 1. Your Aiven Database Details
config = {
    'user': 'avnadmin',
    'password': 'AVNS_qclUfTKSrqQyzmN9pz4',
    'host': 'peer-support-system-fatinshamirah212-93b4.j.aivencloud.com',
    'port': 26591,
    'database': 'defaultdb',
    'ssl_disabled': False  # Aiven requires SSL
}

# 2. Read your SQL file
print("Reading SQL schema...")
with open('db_schema.sql', 'r') as f:
    sql_commands = f.read()

# 3. Connect and Execute
try:
    print("Connecting to Aiven Cloud Database...")
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()
    
    # Split the file into individual commands (semicolons)
    commands = sql_commands.split(';')
    
    for command in commands:
        if command.strip():
            # Skip the specific 'USE peer_support_db' command since we are already in 'defaultdb'
            if 'USE ' in command:
                continue
            cursor.execute(command)
            
    conn.commit()
    print("✅ Success! Tables created in the cloud.")
    
except mysql.connector.Error as err:
    print(f"❌ Error: {err}")
finally:
    if 'conn' in locals() and conn.is_connected():
        conn.close()