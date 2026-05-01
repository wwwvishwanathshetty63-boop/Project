import sys
import os
import json
import requests
from unittest.mock import patch, MagicMock

# Ensure project root is in path
sys.path.insert(0, os.getcwd())

from backend.services.api_key_validator import validate_api_key

def test_validator_scenarios():
    scenarios = [
        {"name": "JSONPlaceholder (Mock API)", "url": "https://jsonplaceholder.typicode.com/posts", "api_key": "dummy-key", "expected_valid": True},
        {"name": "Invalid Endpoint (404)", "url": "https://jsonplaceholder.typicode.com/nonexistent", "api_key": "key", "expected_valid": False},
    ]
    
    print("=== Real API Scenarios ===")
    for s in scenarios:
        print(f"Testing {s['name']}...")
        res = validate_api_key(s['api_key'], s['url'])
        print(f"  Result: {res['key_status']} (is_valid: {res['is_valid']})")
        if res['is_valid'] != s['expected_valid']:
            print(f"  WAINING: Expected {s['expected_valid']} but got {res['is_valid']}")

    print("\n=== Mocked Response Scenarios ===")
    mock_scenarios = [
        {"status": 200, "expected_status": "VALID", "is_valid": True},
        {"status": 401, "expected_status": "INVALID", "is_valid": False},
        {"status": 403, "expected_status": "LIMITED", "is_valid": False},
        {"status": 429, "expected_status": "RATE_LIMITED", "is_valid": False},
        {"status": 500, "expected_status": "INVALID", "is_valid": False}, # Becomes INVALID after retries in current logic
    ]

    for ms in mock_scenarios:
        with patch('requests.Session.request') as mock_req:
            mock_resp = MagicMock()
            mock_resp.status_code = ms['status']
            mock_req.return_value = mock_resp
            
            res = validate_api_key("test-key", "http://example.com")
            print(f"Mocked HTTP {ms['status']} -> Result: {res['key_status']} (is_valid: {res['is_valid']})")
            
            if res['key_status'] != ms['expected_status']:
                 # Exception: 500 might retry and eventually fail as INVALID if retries exhausted
                 if ms['status'] == 500 and res['key_status'] == "INVALID":
                     pass
                 else:
                    print(f"  ERROR: Expected {ms['expected_status']} but got {res['key_status']}")

if __name__ == "__main__":
    test_validator_scenarios()
