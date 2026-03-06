import sqlite3
import os

db_path = r'c:\Users\VISHWANATH SHETTY\Project\api-monitoring-saas\database.db'

def get_token():
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get the latest unused invitation
    cursor.execute("SELECT name, email, token FROM employee_invitations WHERE is_used = 0 ORDER BY created_at DESC LIMIT 1")
    row = cursor.fetchone()
    
    if row:
        print(f"Name: {row[0]}")
        print(f"Email: {row[1]}")
        print(f"Token: {row[2]}")
    else:
        print("No pending invitations found.")
        
    conn.close()

if __name__ == "__main__":
    get_token()
