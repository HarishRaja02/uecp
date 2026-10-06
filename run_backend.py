"""UECP Flask launcher. Run from the repository root: python run_backend.py"""
from pathlib import Path
import os
import sys

backend_dir = Path(__file__).resolve().parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="localhost", port=int(os.getenv("API_PORT", "8001")), debug=False)
