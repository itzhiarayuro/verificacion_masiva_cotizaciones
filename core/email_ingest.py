"""
Email ingestion bridge: turns emails into Jobs + documents in storage.

Used by:
- UI "Ingest from Gmail" button
- workers (simple or Celery periodic task)
- API endpoints
"""
from __future__ import annotations
import logging
from typing import Optional, Dict, Any

from core.email_reader import EmailReader
from core.job_manager import get_job_manager, Job
from core.storage import get_storage

logger = logging.getLogger(__name__)


def ingest_gmail_to_job(
    query: str = "has:attachment filename:pdf",
    max_messages: int = 200,
    llm_mode: str = "fallback",
    notify_email: Optional[str] = None,
    mark_read_after: bool = True,
) -> Job:
    """
    End-to-end: fetch PDFs from Gmail, write them to object storage,
    create a Job with documents registered, ready for workers.
    """
    reader = EmailReader()
    mgr = get_job_manager()
    storage = get_storage()

    job = mgr.create_email_ingest_job(
        query=query,
        account="gmail",
        max_messages=max_messages,
        llm_mode=llm_mode,
        notify_email=notify_email,
    )

    # Fetch + stream directly into storage under the job prefix
    prepared = reader.fetch_and_prepare_for_job(
        query=query,
        max_messages=max_messages,
        storage=storage,
        job_prefix=job.storage_prefix,
    )

    # Register the documents we just wrote to storage
    for item in prepared:
        name = item.get("name")
        key = item.get("storage_key") or f"{job.storage_prefix}/originals/{name}"
        from core.db import add_document_to_job
        add_document_to_job(job.id, filename=name, storage_key=key)

    from core.db import update_job
    update_job(job.id, total_files=len(prepared), status="pending" if prepared else "completed")

    logger.info(f"Email ingest job {job.id} created with {len(prepared)} PDFs from query: {query}")
    return job
