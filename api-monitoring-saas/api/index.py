import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app

# Vercel's Python runtime requires the WSGI app object to be exposed
app = create_app()
