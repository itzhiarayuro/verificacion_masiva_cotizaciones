"""
Celery tasks (and reusable functions) for the job system.

Both the simple DB worker and real Celery workers can call these.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from celery import shared_task
from core.db import init_db, update_job, finalize_and_notify
from core.job_manager import get_job_manager


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def process_job_batch(self, job_id: str, max_files: int = 50):
    """Process a small batch for a job. Can be called repeatedly until the job is complete.
    On final batches, finalize_and_notify will send email + attempt export.
    """
    init_db()
    mgr = get_job_manager()
    try:
        summary = mgr.process_job_small_batch(job_id, max_files=max_files)
        # Always check if this batch finished the job
        finalize_and_notify(job_id, also_export=True)
        return {"job_id": job_id, **summary}
    except Exception as exc:
        # Let Celery retry a few times
        raise self.retry(exc=exc)


@shared_task
def ingest_email_and_create_job(query: str, account: str = "gmail", max_messages: int = 100, llm_mode: str = "fallback"):
    """
    Example periodic or on-demand task: fetch from email, register documents, create job.
    The actual fetching uses the upgraded EmailReader.
    """
    from core.email_reader import EmailReader
    from core.email_sender import EmailSender  # for later notifications
    from core.job_manager import get_job_manager

    init_db()
    reader = EmailReader()
    mgr = get_job_manager()

    # This will be fully wired after email_reader upgrade
    print(f"[tasks] Ingesting emails with query: {query}")
    # For now: the real implementation lives in core/email_ingest.py (created together with full EmailReader)
    # Placeholder return
    return {"status": "not_fully_wired_yet", "query": query}
