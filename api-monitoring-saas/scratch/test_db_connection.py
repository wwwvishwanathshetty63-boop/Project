
import os
import psycopg2
from dotenv import load_dotenv

def test_db():
    load_dotenv()
    url = os.getenv("DATABASE_URL")
    print(f"Testing connection to: {url.split('@')[-1]}")
    try:
        conn = psycopg2.connect(url)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"[+] SUCCESS: Connected to PostgreSQL! Version: {version[0]}")
        
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        tables = cursor.fetchall()
        print(f"[+] Tables found: {[t[0] for t in tables]}")
        
        conn.close()
    except Exception as e:
        print(f"[-] FAILED: {e}")

if __name__ == "__main__":
    test_db()
