"""Worker entrypoints.

- simple_worker.py : DB-polling worker, works with zero extra services (SQLite + local storage).
- celery_app.py + tasks.py : Full Celery + Redis path (recommended for >10k PDFs / production).
"""
