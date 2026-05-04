import os
file_path = r'c:\Users\VISHWANATH SHETTY\Project\api-monitoring-saas\backend\app.py'
dir1 = os.path.dirname(file_path)
dir2 = os.path.dirname(dir1)
frontend = os.path.join(dir2, 'frontend')
print(f"Path 1: {dir1}")
print(f"Path 2: {dir2}")
print(f"Frontend: {frontend}")
print(f"Exists: {os.path.exists(frontend)}")
print(f"Index exists: {os.path.exists(os.path.join(frontend, 'index.html'))}")
