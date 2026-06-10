"""
Simple DB-polling worker for Auditor de Cotizaciones.

Usage (local, no Redis/Celery needed):
    python -m workers.simple_worker --once          # process one batch then exit
    python -m workers.simple_worker                 # loop forever, poll every 5s

It claims pending jobs and processes documents in small batches using JobManager.
Safe to run multiple instances (they race on status=processing but DB updates are fine for starters).
"""
import argparse
import os
import sys
import time
from datetime import datetime

# Make sure we can import from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.db import init_db, get_job, update_job, finalize_job_if_complete, list_jobs
from core.job_manager import get_job_manager


def process_pending_jobs(max_per_job: int = 50, max_jobs: int = 5):
    """Find pending/partial jobs and advance them."""
    mgr = get_job_manager()
    jobs = list_jobs(limit=max_jobs, status=None)

    worked = 0
    for job in jobs:
        if job.status not in ("pending", "processing", "partial"):
            continue

        print(f"[worker] Advancing job {job.id} ({job.source_type}) status={job.status} progress={job.progress_pct}%")

        try:
            # Mark as processing
            update_job(job.id, status="processing")

            summary = mgr.process_job_small_batch(job.id, max_files=max_per_job)
            print(f"[worker]   batch: +{summary.get('processed_in_batch', 0)} files, +{summary.get('new_rows', 0)} rows -> job {summary.get('job_status')}")

            finalize_job_if_complete(job.id)
            j2 = get_job(job.id)
            if j2 and j2.status in ("completed", "partial"):
                print(f"[worker]   JOB FINISHED: {job.id} status={j2.status} total_rows={j2.total_rows}")
                # TODO: send notification email / webhook here (see email_sender + job_manager)
            worked += 1
        except Exception as e:
            print(f"[worker] ERROR on job {job.id}: {e}")
            update_job(job.id, status="failed", error=str(e)[:300])

    return worked


def main_loop(poll_interval: float = 5.0, max_per_job: int = 50):
    print("=== Auditor Simple Worker started ===")
    print(f"DB: {os.getenv('DATABASE_URL') or 'outputs/auditor.db (sqlite)'}")
    print(f"Storage dir: {os.getenv('AUDITOR_STORAGE_DIR') or 'storage'}")
    print(f"LLM default controlled by job.llm_mode + AUDITOR_LLM_MODE env")
    print("Press Ctrl+C to stop.\n")

    init_db()

    try:
        while True:
            n = process_pending_jobs(max_per_job=max_per_job)
            if n == 0:
                # Also try to finalize any stuck jobs
                for j in list_jobs(limit=20):
                    finalize_job_if_complete(j.id)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        print("\n[worker] Shutting down gracefully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Process one batch of pending work then exit")
    parser.add_argument("--poll", type=float, default=5.0, help="Seconds between polls (default 5)")
    parser.add_argument("--batch", type=int, default=50, help="Max documents per job per iteration")
    args = parser.parse_args()

    init_db()

    if args.once:
        process_pending_jobs(max_per_job=args.batch, max_jobs=10)
        print("[worker] One-shot run complete.")
    else:
        main_loop(poll_interval=args.poll, max_per_job=args.batch)
