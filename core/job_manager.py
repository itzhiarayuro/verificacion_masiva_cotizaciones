from __future__ import annotations
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .db import (
    create_job, get_job, list_jobs, update_job, add_document_to_job,
    update_document, add_agent_log, finalize_job_if_complete, finalize_and_notify, get_session
)
from .models import Job, Document
from .storage import get_storage, StorageBackend
from core.extraction.pdf_pipeline import PDFExtractionPipeline, CSV_COLUMNS
from core.observability import set_correlation_id, get_logger

logger = get_logger(__name__)


class JobManager:
    """
    High-level coordinator for massive jobs.
    - Creates jobs + registers documents (PDFs already in storage or uploaded).
    - Provides small-batch processing entrypoint (used by workers).
    - Streams results to Parquet/CSV in storage.
    - Updates DB progress + lightweight agent logs.
    """

    def __init__(self, storage: Optional[StorageBackend] = None, use_llm_default: bool = True):
        self.storage = storage or get_storage()
        self.use_llm_default = use_llm_default

    # ---------- Ingestion ----------

    def create_upload_job(
        self,
        files: List[Dict[str, Any]],  # [{"name": , "bytes": }] or paths
        *,
        llm_mode: str = "fallback",
        batch_size: int = 50,
        notify_email: Optional[str] = None,
        webhook_url: Optional[str] = None,
        max_files_per_subjob: int = 2000,   # auto-split threshold for very large uploads
    ) -> Job:
        """Register an upload-based job. Writes originals to storage if bytes provided.
        If the number of files is very large, it auto-splits into multiple sub-jobs.
        """
        total = len(files)
        if total <= max_files_per_subjob:
            # Normal single job
            job = create_job(
                source_type="upload",
                llm_mode=llm_mode,
                batch_size=batch_size,
                notify_email=notify_email,
                webhook_url=webhook_url,
            )
            set_correlation_id(job.id)
            logger.info("Job created (upload)", extra={"total_files": total, "llm_mode": llm_mode})

            self._register_files_to_job(job, files)
            update_job(job.id, total_files=total, status="pending")
            add_agent_log(job.id, "senior_dev", f"Job created with {total} files (llm_mode={llm_mode})")
            return get_job(job.id)

        # === AUTO SPLIT for massive uploads ===
        parent = create_job(
            source_type="upload",
            source_meta={"auto_split": True, "total_original_files": total, "max_per_subjob": max_files_per_subjob},
            llm_mode=llm_mode,
            batch_size=batch_size,
            notify_email=notify_email,
            webhook_url=webhook_url,
        )
        add_agent_log(parent.id, "senior_dev", f"AUTO-SPLIT iniciado: {total} archivos → sub-jobs de máx {max_files_per_subjob}")

        sub_jobs = []
        for i in range(0, total, max_files_per_subjob):
            chunk = files[i:i + max_files_per_subjob]
            sub = create_job(
                source_type="upload",
                source_meta={"parent_job_id": parent.id, "split_index": i // max_files_per_subjob, "chunk_size": len(chunk)},
                llm_mode=llm_mode,
                batch_size=batch_size,
                notify_email=notify_email,
            )
            self._register_files_to_job(sub, chunk)
            update_job(sub.id, total_files=len(chunk), status="pending")
            add_agent_log(sub.id, "senior_dev", f"Sub-job {sub.id[:8]} creado ({len(chunk)} archivos) del parent {parent.id[:8]}")
            sub_jobs.append(sub.id)

        update_job(parent.id, total_files=total, status="pending", source_meta={
            **(parent.source_meta or {}),
            "sub_job_ids": sub_jobs
        })
        return get_job(parent.id)

    def _register_files_to_job(self, job: Job, files: List[Dict[str, Any]]):
        prefix = job.storage_prefix
        for f in files:
            name = f.get("name") or f"file_{uuid.uuid4().hex[:8]}.pdf"
            key = f"{prefix}/originals/{name}"
            if "bytes" in f and f["bytes"]:
                self.storage.put_bytes(key, f["bytes"])
            elif "path" in f:
                self.storage.put_file(key, f["path"])
            add_document_to_job(job.id, filename=name, storage_key=key)

    def create_email_ingest_job(
        self,
        *,
        query: str,
        account: str = "gmail",
        max_messages: int = 200,
        llm_mode: str = "fallback",
        notify_email: Optional[str] = None,
        max_files_per_subjob: int = 2000,
    ) -> Job:
        """Create a job that will be filled by the email ingestion worker.
        Supports auto-split for very large email result sets.
        """
        job = create_job(
            source_type="email",
            source_meta={"query": query, "account": account, "max_messages": max_messages},
            llm_mode=llm_mode,
            notify_email=notify_email,
        )
        set_correlation_id(job.id)
        logger.info("Job created (email ingest)", extra={"query": query})
        add_agent_log(job.id, "senior_dev", f"Email ingest job created. query={query}")
        return job

    # Note: actual splitting for email happens in email_ingest.py after fetching the list of attachments.
    # See core/email_ingest.py for the chunking logic that calls create_upload_job style registration.

    # ---------- Processing (small batch, stream to storage) ----------

    def process_document(
        self,
        job_id: str,
        doc_id: int,
        *,
        on_progress: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """Process ONE document. Called by worker in a loop (small batches)."""
        job = get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        with get_session() as s:
            doc = s.get(Document, doc_id)
            if not doc:
                raise ValueError(f"Document {doc_id} not found")

        update_document(doc_id, status="processing")
        add_agent_log(job_id, "pdf_analyst", f"Processing {doc.filename}")

        # Get PDF bytes (prefer local path if available)
        local_path = self.storage.get_local_path(doc.storage_key)
        if local_path and os.path.exists(local_path):
            with open(local_path, "rb") as f:
                pdf_bytes = f.read()
        else:
            pdf_bytes = self.storage.get_bytes(doc.storage_key)

        # Decide LLM usage from job
        llm_mode = (job.llm_mode or "fallback").lower()
        use_llm = self._should_use_llm(llm_mode)

        pipeline = PDFExtractionPipeline(use_llm=use_llm)

        def progress_cb(agent_id: str, msg: str):
            add_agent_log(job_id, agent_id, msg)
            if on_progress:
                on_progress(agent_id, msg)

        try:
            rows = pipeline.process_pdf_bytes(doc.filename, pdf_bytes, on_progress=progress_cb)

            # Write results shard (Parquet preferred, fallback CSV)
            result_key = self._write_result_shard(job, doc, rows)

            # QA (light)
            qa = self._light_qa(rows)

            update_document(
                doc_id,
                status="completed",
                row_count=len(rows),
                extraction_method="table+ia" if use_llm else "table",
                qa_passed=qa.get("passed", 0),
                qa_rate=qa.get("pass_rate", 100.0),
                preview_json=rows[:8] if rows else [],
                processed_at=__import__("datetime").datetime.utcnow(),
            )

            # Roll up to job
            self._rollup_job_stats(job_id, added_rows=len(rows))

            add_agent_log(job_id, "data_engineer", f"{len(rows)} rows written for {doc.filename} -> {result_key}")

            return {"rows": len(rows), "result_key": result_key, "qa": qa}

        except Exception as exc:
            # For corrupt shards we already return a special error row from the pipeline,
            # so we mark as partial failure but continue the batch (do not re-raise).
            is_corrupt = "CORRUPTO" in str(exc) or "SHARD" in str(exc) or "Error lectura" in str(exc)
            update_document(doc_id, status="failed", error=str(exc)[:500])
            add_agent_log(job_id, "senior_dev", f"FAILED {doc.filename}: {exc}", status="failed")

            # Update job-level corrupt counter (using source_meta as lightweight store)
            try:
                job = get_job(job_id)
                if job:
                    meta = dict(job.source_meta or {})
                    meta["corrupt_shards"] = meta.get("corrupt_shards", 0) + 1
                    update_job(job_id, source_meta=meta)
            except Exception:
                pass

            if not is_corrupt:
                # Only re-raise real unexpected errors so the batch can continue for corrupt ones
                raise

    def process_job_small_batch(
        self,
        job_id: str,
        *,
        max_files: int = 50,
        on_event: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Process up to max_files pending documents for this job.
        This is the main entrypoint for simple_worker and Celery tasks.
        Returns summary; caller should loop until job is done.
        """
        job = get_job(job_id)
        if not job:
            return {"error": "job not found"}

        update_job(job_id, status="processing")

        from sqlalchemy import select
        from .db import SessionLocal
        with SessionLocal() as s:
            pending_docs = list(
                s.scalars(
                    select(Document)
                    .where(Document.job_id == job_id, Document.status == "pending")
                    .limit(max_files)
                ).all()
            )

        processed = 0
        total_new_rows = 0
        for d in pending_docs:
            try:
                res = self.process_document(job_id, d.id)
                processed += 1
                total_new_rows += res.get("rows", 0)
                if on_event:
                    on_event({"type": "file_done", "doc_id": d.id, "filename": d.filename, "rows": res.get("rows", 0)})
            except Exception as e:
                if on_event:
                    on_event({"type": "file_failed", "doc_id": d.id, "error": str(e)})

        # Check completion + trigger email/export if ready
        finalize_and_notify(job_id, also_export=True)

        # Update totals
        j = get_job(job_id)
        return {
            "job_id": job_id,
            "processed_in_batch": processed,
            "new_rows": total_new_rows,
            "job_status": j.status if j else "unknown",
            "job_progress": j.progress_pct if j else 0,
        }

    # ---------- Result writing ----------

    def _write_result_shard(self, job: Job, doc: Document, rows: List[Dict[str, Any]]) -> str:
        if not rows:
            return ""
        df = pd.DataFrame(rows)

        # Ensure all expected columns exist (for consistent Parquet schema)
        for col in CSV_COLUMNS:
            if col not in df.columns:
                df[col] = "NO ESPECIFICADO"

        df = df[CSV_COLUMNS]  # stable order

        base = f"{job.storage_prefix}/results/{Path(doc.filename).stem}"
        parquet_key = f"{base}.parquet"
        csv_key = f"{base}.csv"

        try:
            # Parquet (best)
            buf = df.to_parquet(index=False)
            self.storage.put_bytes(parquet_key, buf, content_type="application/parquet")
            # Also write a small CSV for easy human inspection
            self.storage.put_bytes(csv_key, df.to_csv(index=False).encode("utf-8"), content_type="text/csv")
            return parquet_key
        except Exception:
            # Fallback: CSV only
            self.storage.put_bytes(csv_key, df.to_csv(index=False).encode("utf-8"), content_type="text/csv")
            return csv_key

    def _light_qa(self, rows: List[Dict]) -> Dict[str, Any]:
        # Reuse the spirit of LiveQARunner without importing heavy deps here
        if not rows:
            return {"passed": 0, "total": 1, "pass_rate": 0.0, "status": "FAIL"}
        required = ["Cód. Item Archivo", "Proveedor", "Descripción del Producto"]
        bad = sum(1 for r in rows if any(not str(r.get(f, "")).strip() for f in required))
        passed = 1 if bad == 0 else 0
        rate = 100.0 if bad == 0 else max(0, 100 - (bad / len(rows) * 30))
        return {"passed": passed, "total": 1, "pass_rate": round(rate, 1), "status": "PASS" if passed else "WARN"}

    def _should_use_llm(self, llm_mode: str) -> bool:
        if llm_mode == "none":
            return False
        if llm_mode == "always":
            return True
        # fallback (default)
        return self.use_llm_default

    def _rollup_job_stats(self, job_id: str, added_rows: int = 0):
        with get_session() as s:
            job = s.get(Job, job_id)
            if not job:
                return
            # Count completed docs
            from sqlalchemy import select, func
            completed = s.scalar(
                select(func.count(Document.id))
                .where(Document.job_id == job_id, Document.status == "completed")
            ) or 0
            total_rows = s.scalar(
                select(func.sum(Document.row_count)).where(Document.job_id == job_id)
            ) or 0

            job.processed_files = completed
            job.total_rows = total_rows + added_rows  # safety
            s.commit()


# Convenience singleton for simple cases
_default_manager: Optional[JobManager] = None

def get_job_manager() -> JobManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = JobManager()
    return _default_manager


# ---------- High-level export helper exposed via JobManager ----------

def export_consolidated_for_job(
    job_id: str,
    formats: List[str] = ("parquet", "xlsx"),
    low_memory: bool = True,
    filter_proveedor: Optional[str] = None,
    filter_fecha_desde: Optional[str] = None,
    group_by: Optional[str] = None,
) -> dict:
    """
    Rich export result for massive jobs.
    Supports filters and group_by for incremental exports.
    """
    from .export import export_consolidated
    return export_consolidated(
        job_id,
        formats=formats,
        low_memory=low_memory,
        filter_proveedor=filter_proveedor,
        filter_fecha_desde=filter_fecha_desde,
        group_by=group_by,
    )


def safe_export_consolidated(job_id: str, **kwargs) -> dict:
    """Wrapper that never raises. Always returns a result dict even on total failure."""
    try:
        return export_consolidated_for_job(job_id, **kwargs)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.exception(f"safe_export_consolidated hard failure for {job_id}")
        return {
            "success": False,
            "primary_key": None,
            "errors": [{"fatal": str(e)[:500]}],
            "shards_ok": 0,
            "shards_failed": -1,
        }


# ---------- Celery / enqueue support (Phase 2) ----------

def is_celery_available() -> bool:
    """Safer detection: package present + Redis actually reachable (best effort)."""
    try:
        import redis
        r = redis.Redis.from_url(os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"), socket_connect_timeout=1)
        r.ping()
        from workers import celery_app  # noqa
        return True
    except Exception:
        return False


def enqueue_job_batch(job_id: str, max_files: int = 50, force_celery: bool = False) -> dict:
    """
    Enqueue via Celery if available, otherwise process a first batch directly
    (so the simple_worker or the current process can continue).
    Returns info about what happened.
    """
    if force_celery or is_celery_available():
        try:
            from workers.tasks import process_job_batch
            res = process_job_batch.delay(job_id, max_files)
            update_job(job_id, status="processing")
            return {"mode": "celery", "task_id": str(res.id), "job_id": job_id}
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Celery enqueue failed, falling back to direct: {e}")

    # Fallback: process first batch right now (simple_worker will pick up the rest)
    mgr = get_job_manager()
    summary = mgr.process_job_small_batch(job_id, max_files=max_files)
    return {"mode": "direct", "summary": summary, "job_id": job_id}
