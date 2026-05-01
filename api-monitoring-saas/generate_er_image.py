import base64
import urllib.request
import urllib.parse
import os

mermaid_code = """
erDiagram
    USERS {
        TEXT id PK
        TEXT name
        TEXT email
        TEXT password_hash
        TEXT role
        TEXT company_id FK
        TEXT employee_id
        TIMESTAMP created_at
    }

    EMPLOYEE_INVITATIONS {
        TEXT id PK
        TEXT company_id FK
        TEXT name
        TEXT email
        TEXT token
        BOOLEAN is_used
        TIMESTAMP created_at
    }

    API_ENDPOINTS {
        TEXT id PK
        TEXT user_id FK
        TEXT created_by FK
        TEXT name
        TEXT url
        TEXT method
        INTEGER interval
        BOOLEAN is_active
        TEXT api_key
        TEXT api_key_header
        TEXT auth_type
        TEXT key_status
        TIMESTAMP last_validated_at
        TIMESTAMP created_at
    }

    MONITORING_LOGS {
        TEXT id PK
        TEXT endpoint_id FK
        INTEGER status_code
        REAL response_time
        BOOLEAN is_success
        TEXT api_key_status
        TIMESTAMP checked_at
    }
    
    EMAIL_VERIFICATIONS {
        TEXT id PK
        TEXT email
        TEXT otp
        BOOLEAN is_used
        TIMESTAMP expires_at
        TIMESTAMP created_at
    }

    USERS ||--o{ USERS : "employs"
    USERS ||--o{ EMPLOYEE_INVITATIONS : "creates"
    USERS ||--o{ API_ENDPOINTS : "owns"
    USERS ||--o{ API_ENDPOINTS : "creates"
    API_ENDPOINTS ||--o{ MONITORING_LOGS : "generates"
"""

try:
    # Base64 encode the mermaid code
    encoded_str = base64.urlsafe_b64encode(mermaid_code.encode('utf-8')).decode('ascii')
    
    # Construct the URL
    url = f"https://mermaid.ink/img/{encoded_str}?type=png&bgColor=!white"
    
    # Download the image
    output_path = "ER_Diagram.png"
    print(f"Downloading ER Diagram from {url}")
    
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response, open(output_path, 'wb') as out_file:
        out_file.write(response.read())
        
    print(f"Successfully saved to {output_path}")
except Exception as e:
    print(f"Error: {e}")
