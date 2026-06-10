
## Phase 3: Corrupt shards, Auto-split, Incremental exports (executed)

User requested: "si, hazlo todo" for the three examples.

**Implemented:**

- **Mejor manejo de shards corruptos en la lectura del pipeline**
  - `pdf_pipeline.py`: `process_pdf_bytes` now catches any exception (corrupt PDF, bad bytes, pdfplumber crash, etc.) and returns a single traceable error row instead of raising.
  - `job_manager.py`: `process_document` marks the Document as failed, records in job.source_meta["corrupt_shards"], and only re-raises for non-corrupt errors so the batch/job continues.
  - Agent "security" / "senior_dev" logs the failure.
  - Job and Document keep full error text.

- **Split automático de jobs grandes**
  - `create_upload_job` now accepts `max_files_per_subjob` (default 2000).
  - If upload > threshold → creates a parent job + multiple sub-jobs (linked via source_meta).
  - Email ingest (`email_ingest.py` + `create_email_ingest_job`) also chunks and creates sub-jobs for huge inbox pulls.
  - UI and API creation now expose / respect the threshold.
  - Parent job stores list of sub_job_ids and total count.
  - Workers process subs independently.

- **Export incremental / filtrado / agrupado por proveedor/fecha**
  - `export_consolidated` now supports:
    - `filter_proveedor="PAVCO"`
    - `filter_fecha_desde="2025/06"`
    - `group_by="Proveedor"` → produces many smaller `job_xxx_group_PAVCO.parquet` files instead of one monster.
  - Works with the existing low_memory engine.
  - Rich result + manifest updated with applied filters.
  - Exposed in API (`/jobs/{id}/export` accepts the filter params) and in UI page 10 (text inputs + group selector + "Export FILTRADO / AGRUPADO" button).
  - Perfect for negotiation: export only one provider's data without touching the 20M row monster.

All changes keep backward compatibility. Existing small jobs and legacy flows are untouched. Corrupt handling + splits + filtered exports are designed for the 1M+ PDF reality.

See updated code in:
- core/extraction/pdf_pipeline.py
- core/job_manager.py
- core/email_ingest.py
- core/export.py
- api/main.py
- ui/pages/09_jobs_y_email.py
- core/models.py + core/db.py (for new columns + migration)

**Next possible (if user asks):** full parent/child job tree UI, scheduled incremental exports via Celery beat, automatic re-ingest of only failed/corrupt documents, etc.
