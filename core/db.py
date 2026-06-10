from __future__ import annotations
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, select, update, func
from sqlalchemy.orm import Session, sessionmaker

from .models import Base, Job, Document, ExtractedItem


# Default to local SQLite for zero-config. Override with DATABASE_URL=postgresql://...
DEFAULT_DB_PATH = os.getenv("AUDITOR_DB_PATH", "outputs/auditor.db")
DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{DEFAULT_DB_PATH}"

# For SQLite we need check_same_thread=False for multi-thread (workers + UI)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Create tables if they don't exist. Call on startup."""
    os.makedirs(os.path.dirname(DEFAULT_DB_PATH) if "/" in DEFAULT_DB_PATH or "\\" in DEFAULT_DB_PATH else "outputs", exist_ok=True)
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    return SessionLocal()


# ---------- Job helpers ----------

def create_job(
    *,
    source_type: str = "upload",
    source_meta: Optional[Dict[str, Any]] = None,
    llm_mode: str = "fallback",
    batch_size: int = 50,
    webhook_url: Optional[str] = None,
    notify_email: Optional[str] = None,
    storage_prefix: Optional[str] = None,
) -> Job:
    job_id = str(uuid.uuid4())
    with get_session() as s:
        job = Job(
            id=job_id,
            source_type=source_type,
            source_meta=source_meta or {},
            llm_mode=llm_mode,
            batch_size=batch_size,
            webhook_url=webhook_url,
            notify_email=notify_email,
            storage_prefix=storage_prefix or f"jobs/{job_id[:2]}/{job_id}",
            status="pending",
            agent_logs=[],
        )
        s.add(job)
        s.commit()
        s.refresh(job)
        return job


def get_job(job_id: str) -> Optional[Job]:
    with get_session() as s:
        return s.get(Job, job_id)


def list_jobs(limit: int = 50, status: Optional[str] = None) -> List[Job]:
    with get_session() as s:
        stmt = select(Job).order_by(Job.created_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(Job.status == status)
        return list(s.scalars(stmt).all())


def update_job(job_id: str, **fields: Any) -> Optional[Job]:
    with get_session() as s:
        job = s.get(Job, job_id)
        if not job:
            return None
        for k, v in fields.items():
            if hasattr(job, k):
                setattr(job, k, v)
        if "processed_files" in fields or "total_files" in fields:
            total = job.total_files or 0
            proc = job.processed_files or 0
            job.progress_pct = round((proc / total * 100), 1) if total > 0 else 0.0
        s.commit()
        s.refresh(job)
        return job


def add_document_to_job(
    job_id: str,
    *,
    filename: str,
    storage_key: str,
) -> Document:
    with get_session() as s:
        doc = Document(
            job_id=job_id,
            filename=filename,
            storage_key=storage_key,
            status="pending",
        )
        s.add(doc)
        # bump total on job
        job = s.get(Job, job_id)
        if job:
            job.total_files = (job.total_files or 0) + 1
        s.commit()
        s.refresh(doc)
        return doc


def update_document(doc_id: int, **fields: Any) -> Optional[Document]:
    with get_session() as s:
        doc = s.get(Document, doc_id)
        if not doc:
            return None
        for k, v in fields.items():
            if hasattr(doc, k):
                setattr(doc, k, v)
        if "row_count" in fields:
            # also roll up to job total_rows (simple)
            job = s.get(Job, doc.job_id)
            if job:
                # naive: recount or just add delta — here we set absolute for simplicity in worker
                pass
        s.commit()
        s.refresh(doc)
        return doc


def add_agent_log(job_id: str, agent_id: str, message: str, status: str = "active") -> None:
    """Append a lightweight agent-style event (kept small, last ~50)."""
    with get_session() as s:
        job = s.get(Job, job_id)
        if not job:
            return
        logs = list(job.agent_logs or [])
        logs.append({
            "ts": datetime.utcnow().isoformat(),
            "agent_id": agent_id,
            "message": message,
            "status": status,
        })
        # keep bounded
        job.agent_logs = logs[-80:]
        s.commit()


def finalize_job_if_complete(job_id: str) -> Optional[Job]:
    with get_session() as s:
        job = s.get(Job, job_id)
        if not job:
            return None
        docs = list(s.scalars(select(Document).where(Document.job_id == job_id)).all())
        completed = [d for d in docs if d.status in ("completed", "failed")]
        if len(completed) >= (job.total_files or 0) and job.total_files > 0:
            failed = [d for d in docs if d.status == "failed"]
            job.status = "completed" if not failed else "partial"
            job.progress_pct = 100.0
            s.commit()
            s.refresh(job)
        return job
