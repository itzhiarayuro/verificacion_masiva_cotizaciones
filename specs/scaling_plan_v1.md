# Scaling & Production Plan: Auditor de Cotizaciones V3 → 1M PDFs + Full Email

**Date:** 2026 (current session)  
**Scope:** Execute the 5 priorities for massive scale + complete email integration.  
**Current state summary:** Excellent extraction pipeline + simulated 24-agent team + partial email + in-memory everything. Great for <5k PDFs locally. Not ready for 1M or unattended email ingestion.

## Goals
- Handle 1M+ PDFs reliably (chunked, resumable, observable).
- Real email ingestion (Gmail primary, Outlook later) + notifications (send results/alerts).
- Drastically lower LLM cost/latency (tables-first, configurable modes).
- Real persistence, object storage abstraction, task distribution.
- Keep current "small batch local mode" working (Streamlit drag & drop for 10-500 files).
- UI for configuring and monitoring jobs + email sources.

## Key Architectural Decisions (pragmatic for Windows/local-first)

1. **Persistence**: SQLAlchemy + SQLite by default (`outputs/auditor.db`). Easy zero-config. Env var `DATABASE_URL` for Postgres later. No Alembic in v1 (simple `init_db()` + `CREATE TABLE IF NOT EXISTS`).

2. **Object Storage**:
   - Abstract interface `core/storage/base.py`.
   - Default impl: `LocalShardedStorage` — sharded folders under `storage/pdfs/{job_prefix}/{job_id}/original/`, `results/` for Parquet/CSV per document or per job.
   - Ready for MinIO: `MinioStorage` (add `minio` package). Docker service provided.
   - PDFs are written once on ingest, read by workers, never full bytes in long-lived memory.

3. **Task Queue**:
   - Primary for scale: **Celery + Redis** (full power, `docker-compose` support).
   - "Similar" fallback that always works locally: **Simple DB-polling worker** (`workers/simple_worker.py`). Polls `jobs` table for `pending` jobs, claims them, processes in small batches, updates progress. No extra services needed for dev/demo.
   - Both share the same task functions where possible.

4. **Row storage for millions**:
   - `jobs` + `documents` (one row per PDF) in relational DB (status, counts, metadata, storage keys).
   - Extracted rows: **Parquet files** written to storage (highly efficient, compressible, queryable with DuckDB/pandas later). 
   - For live preview / small samples: load Parquet head or keep a small `preview_rows` JSON in DB per document.
   - Optional: `extracted_items` table for very small jobs or when relational queries needed.

5. **LLM reduction**:
   - Job-level `llm_mode`: `none` (default for mass), `fallback` (current behavior: only if <3 good table rows), `always`.
   - Pipeline strengthened to trust table_extractor + markitdown first.
   - Global env `AUDITOR_LLM_MODE=none` or per-job override.
   - Result: 90%+ of files avoid LLM calls.

6. **Email**:
   - Full Gmail: pagination, date/from filters, modify scope (mark read, labels), send scope.
   - New `EmailSender` (reuses Gmail creds or SMTP fallback).
   - Ingestion as a special job type or dedicated task: `ingest_email_source(job_id or config)`.
   - After processing a source: optional "send summary email" with link or attached small Excel + storage path to full Parquet.

7. **Backward compat**:
   - Old in-memory path (Streamlit direct + API `/upload-files`) stays for small interactive use.
   - New path: "Create Job" → enqueue → workers process → results in storage + DB.
   - UI pages gradually migrate to show jobs.

8. **Windows notes**:
   - Redis/Celery: recommend Docker Desktop or WSL2. Simple worker works natively.
   - Auth flows (Gmail local server) work on Windows.

## Data Model (SQLAlchemy)

```python
# jobs
id, created_at, status (pending/processing/completed/failed), total_files, processed_files, 
total_rows, llm_mode, source_type (upload/email/api), source_meta (json), 
storage_prefix, result_parquet_key (or manifest), 
webhook_url, notify_email, error, progress_pct

# documents
id, job_id, filename, storage_key (original pdf), 
status, row_count, page_count, method (markitdown+...), 
qa_passed, qa_rate, preview_json, error, processed_at

# (optional) extracted_items for small jobs or indexing — columns match CSV_COLUMNS
```

Results live primarily as Parquet (one per document or concatenated per job).

## Job Flow (new happy path)

1. Ingest (upload / email worker / api) → write PDF to storage → create Job + Document rows (pending).
2. Enqueue `process_job(job_id)` or per-document tasks.
3. Worker claims job → for each pending document in small batches (e.g. 50):
   - Download bytes (or stream path) from storage.
   - Run pipeline (with llm_mode).
   - Stream rows → write Parquet shard for the document.
   - Update document + job counters + agent-style logs (stored in DB or small log file in storage).
   - Emit progress (for UI polling or WS later).
4. On job complete: build manifest, optional send email, call webhook.
5. UI polls `/jobs/{id}/status` or reads DB.

The 24-agent roster stays as **observability** — we persist per-document "agent activity" summary.

## Files / Components to Create or Heavily Modify

**New:**
- `core/storage/__init__.py`, `base.py`, `local.py`, `minio.py`
- `core/db.py` (engine, session, models in `core/models.py`)
- `core/job_manager.py` (create_job, get_job, update_progress, list_jobs, enqueue helper)
- `core/email_sender.py`
- `workers/simple_worker.py` (and `workers/celery_app.py`, `workers/tasks.py`)
- `ui/pages/09_configuracion.py` (or integrate into existing; new nav page for Email + Job defaults)
- `docker-compose.yml` (redis, minio, optional postgres)
- `init_db.py` or function in db.py

**Modify:**
- `requirements.txt`
- `core/email_reader.py` (major upgrade)
- `core/extraction/pdf_pipeline.py` (llm_mode support, streaming support)
- `core/agents/team_orchestrator.py` (adapt or wrap for job context; keep old API)
- `api/main.py` + schemas (create job endpoints, use job_manager)
- `ui/pages/02_origen_datos.py` (real Gmail connect + "Create Job from Email")
- `ui/pages/05_procesamiento_live.py` (offer "Process as Job" + show job progress for large)
- `ui/pages/08_equipo_agentes.py` (show per-job agent activity from logs)
- `app.py` (add new config page to nav)
- `run_api.py`, install scripts if needed
- `README.md` + `specs/`

**Optional later:** `api/jobs.py` router, real webhooks improvements, Parquet manifest reader for export page.

## Phasing inside this execution

Priority order (as user listed):
1. Persistencia + Celery/similar + object storage   (foundation)
2. EmailReader full + send + ingestion worker
3. Refactor process_batch → small batches + streaming
4. LLM reduction (can be done early, low risk)
5. Real UI config for email/jobs

We will implement in logical build order: infra first (storage/db), then processing refactor, LLM config, email, then UI surfaces.

## Risks & Mitigations
- Breaking current small use: keep old code paths + feature flag / "use_new_job_system" in session.
- Redis on Windows: simple_worker always available; document docker.
- Millions of rows: Parquet primary, avoid loading full into pandas in worker/UI.
- Auth: Gmail OAuth desktop flow works but users must have credentials.json (documented).
- LLM cost: default `none` for mass jobs; visible in UI.

## Success Criteria (for this plan execution)
- Can create a Job from local upload or (mock) email.
- Worker (simple) processes it in small batches, writes Parquets to storage/, updates DB.
- Old drag-and-drop still produces results in Streamlit for <100 files.
- Real Gmail connect (if user has credentials.json) lists real messages, enqueues ingest.
- Can configure llm_mode per job.
- Send email works from results.
- Progress visible in new config/jobs UI.
- No full LLM calls on "fast" mode for table-heavy PDFs.

---

**Next:** Execute via todos. Start with plan-00 complete (this doc), then infra (01-03), processing changes, email, UI.
