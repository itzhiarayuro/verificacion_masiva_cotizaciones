from __future__ import annotations
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .db import (
    create_job, get_job, list_jobs, update_job, add_document_to_job,
    update_document, add_agent_log, finalize_job_if_complete, get_session
)
from .models import Job, Document
from .storage import get_storage, StorageBackend
from core.extraction.pdf_pipeline import PDFExtractionPipeline, CSV_COLUMNS


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
    ) -> Job:
        """Register an upload-based job. Writes originals to storage if bytes provided."""
        job = create_job(
            source_type="upload",
            llm_mode=llm_mode,
            batch_size=batch_size,
            notify_email=notify_email,
            webhook_url=webhook_url,
        )
        prefix = job.storage_prefix

        for f in files:
            name = f.get("name") or f"file_{uuid.uuid4().hex[:8]}.pdf"
            key = f"{prefix}/originals/{name}"

            if "bytes" in f and f["bytes"]:
                self.storage.put_bytes(key, f["bytes"])
            elif "path" in f:
                self.storage.put_file(key, f["path"])

            add_document_to_job(job.id, filename=name, storage_key=key)

        update_job(job.id, total_files=len(files), status="pending")
        add_agent_log(job.id, "senior_dev", f"Job created with {len(files)} files (llm_mode={llm_mode})")
        return get_job(job.id)  # refreshed

    def create_email_ingest_job(
        self,
        *,
        query: str,
        account: str = "gmail",
        max_messages: int = 200,
        llm_mode: str = "fallback",
        notify_email: Optional[str] = None,
    ) -> Job:
        """Create a job that will be filled by the email ingestion worker."""
        job = create_job(
            source_type="email",
            source_meta={"query": query, "account": account, "max_messages": max_messages},
            llm_mode=llm_mode,
            notify_email=notify_email,
        )
        add_agent_log(job.id, "senior_dev", f"Email ingest job created. query={query}")
        return job

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
            update_document(doc_id, status="failed", error=str(exc)[:500])
            add_agent_log(job_id, "senior_dev", f"FAILED {doc.filename}: {exc}", status="failed")
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

        # Check completion
        finalize_job_if_complete(job_id)

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
