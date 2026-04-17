import os
import smtplib
import sys
from dotenv import load_dotenv

def test_smtp():
    load_dotenv()
    
    log_file = "smtp_test_result.txt"
    
    with open(log_file, "w") as f:
        host = os.getenv("SMTP_HOST")
        port = int(os.getenv("SMTP_PORT", 587))
        user = os.getenv("SMTP_USERNAME")
        password = os.getenv("SMTP_PASSWORD")
        
        f.write(f"--- SMTP Configuration Check ---\n")
        f.write(f"Host: {host}\n")
        f.write(f"Port: {port}\n")
        f.write(f"User: {user}\n")
        
        if not password or "INSERT_NEW" in password:
            f.write("\n[!] ERROR: You haven't updated your SMTP_PASSWORD in the .env file yet.\n")
            return

        f.write("\nAttempting to connect to SMTP server...\n")
        try:
            server = smtplib.SMTP(host, port, timeout=15)
            server.set_debuglevel(1) # Enabling debug to log file
            
            # Capture stdout for smtplib debug
            old_stdout = sys.stdout
            sys.stdout = f
            
            try:
                server.starttls()
                server.login(user, password)
                sys.stdout = old_stdout
                f.write("\n[+] SUCCESS: SMTP connection and login successful!\n")
                server.quit()
            except Exception as login_err:
                sys.stdout = old_stdout
                f.write(f"\n[-] LOGIN FAILED: {str(login_err)}\n")
        except Exception as conn_err:
            f.write(f"\n[-] CONNECTION FAILED: {str(conn_err)}\n")

if __name__ == "__main__":
    test_smtp()
