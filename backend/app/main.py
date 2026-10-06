"""Flask development entrypoint. Works from the project root with:
    python backend\\app\\main.py
"""
import sys
import os
from pathlib import Path

# When this file is executed directly, Python puts backend/app on sys.path.
# Add backend so the application package can be imported reliably.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app  # noqa: E402

app = create_app()


if __name__ == "__main__":
    app.run(host="localhost", port=int(os.getenv("API_PORT", "8001")), debug=False)
