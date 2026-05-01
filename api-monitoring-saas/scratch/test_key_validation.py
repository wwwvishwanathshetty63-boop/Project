import sys
import os
import json

# Ensure project root is in path
sys.path.insert(0, os.getcwd())

from backend.services.api_key_validator import validate_api_key, mask_api_key

def test_validator():
    url = "https://jsonplaceholder.typicode.com/posts"
    dummy_key = "dummy-fake-key-12345"
    
    print(f"Testing URL: {url}")
    print(f"Testing with dummy key: {dummy_key}")
    
    result = validate_api_key(
        api_key=dummy_key,
        url=url,
        method="GET",
        api_key_header="Authorization"
    )
    
    print("\n=== Validation Result ===")
    print(json.dumps(result, indent=2))
    
    print(f"\nMasked key check: {mask_api_key(dummy_key)}")

if __name__ == "__main__":
    test_validator()
