import sys
import os

# Ensure backend root directory is in python search path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app

# Vercel serverless function entrypoint
__all__ = ["app"]
