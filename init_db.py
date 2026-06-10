"""
One-time (or on startup) DB initializer for the new job system.
Run: python init_db.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.db import init_db

if __name__ == "__main__":
    print("Initializing Auditor DB (SQLite by default, or DATABASE_URL)...")
    init_db()
    print("Done. Tables created (jobs, documents, extracted_items if used).")
    print("You can now run the simple worker: python -m workers.simple_worker")
