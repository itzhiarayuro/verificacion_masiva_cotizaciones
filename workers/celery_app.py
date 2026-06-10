"""
Celery app definition (optional, for high-scale deployments).

To use:
  1. Have Redis running (docker or native)
  2. pip install -r requirements.txt (includes celery[redis])
  3. Start worker:   celery -A workers.celery_app worker --loglevel=info -Q default -c 4
  4. (optional) beat for periodic email ingest: celery -A workers.celery_app beat ...

The tasks are defined in workers/tasks.py so the simple_worker and Celery can share logic.
"""
import os
from celery import Celery

broker = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

celery_app = Celery(
    "auditor_cotizaciones",
    broker=broker,
    backend=backend,
    include=["workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600 * 2,  # 2h hard limit per task
)
