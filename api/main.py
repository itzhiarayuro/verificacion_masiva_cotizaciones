from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File, Form
from typing import List, Optional
import uuid
import os
import logging
from pathlib import Path
import tempfile
import shutil

from .schemas import (
    UploadRequest, UploadResponse, StatusResponse, WebhookPayload,
    ResultResponse
)
from .webhooks import send_webhook

# Import real pipeline (the same one used by the UI + 24-agent team)
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))
from core.agents.team_orchestrator import AgentTeamOrchestrator
from core.job_manager import get_job_manager
from core.db import init_db

app = FastAPI(
    title="Auditor de Cotizaciones API - Real + Jobs",
    description="API REST + nuevo sistema de Jobs escalable (JobManager + workers). "
                "Legacy in-memory paths preserved for small interactive use. "
                "Usa el mismo pipeline de 24-agentes + extracción Grok-style.",
    version="4.0.0"
)

# In-memory session store (for demo/small use; production uses Job + DB)
sessions_db = {}
logger = logging.getLogger(__name__)

# Initialize new DB on API startup (safe, idempotent)
init_db()
job_mgr = get_job_manager()


def _load_pdf_bytes_from_paths(paths: List[str]) -> List[dict]:
    """Carga bytes desde rutas en disco (UploadRequest legacy mode)."""
    out = []
    for p in paths:
        pth = Path(p)
        if pth.exists() and pth.is_file():
            with open(pth, "rb") as f:
                out.append({"name": pth.name, "bytes": f.read()})
        else:
            logger.warning(f"Archivo no encontrado para API: {p}")
    return out


def _process_real_batch(pdf_list: List[dict], session_id: str, webhook_url: Optional[str] = None):
    """Ejecuta el pipeline real (AgentTeamOrchestrator) y guarda resultados."""
    sessions_db[session_id]["status"] = "processing"
    sessions_db[session_id]["processed"] = 0

    try:
        # use_llm depende de si hay clave (igual que en la UI)
        use_llm = bool(os.getenv("GEMINI_API_KEY"))
        orchestrator = AgentTeamOrchestrator(use_llm=use_llm)

        def on_event(evt):
            # Podemos actualizar progreso granular si quisiéramos
            if evt.get("type") == "file_done":
                sessions_db[session_id]["processed"] = evt.get("index", sessions_db[session_id].get("processed", 0))

        result = orchestrator.process_batch(pdf_list, on_event=on_event)

        sessions_db[session_id].update({
            "status": "completed",
            "processed": result.get("total_files", len(pdf_list)),
            "total_rows": result.get("total_rows", 0),
            "rows": result.get("rows", []),
            "qa": result.get("global_qa", {}),
            "columns": result.get("columns", []),
        })

        if webhook_url:
            payload = WebhookPayload(
                session_id=session_id,
                status="completed",
                results_url=f"/api/v1/cotizaciones/{session_id}/resultados",
                data=result.get("rows", [])[:5],  # muestra pequeña
            )
            send_webhook(str(webhook_url), payload.dict())

    except Exception as exc:
        logger.exception("Error en procesamiento real vía API")
        sessions_db[session_id]["status"] = "failed"
        sessions_db[session_id]["error"] = str(exc)


@app.post("/api/v1/cotizaciones/upload", response_model=UploadResponse)
async def upload_cotizaciones(request: UploadRequest, background_tasks: BackgroundTasks):
    """Modo JSON con rutas (el servidor debe tener acceso a los archivos)."""
    if not request.files:
        raise HTTPException(status_code=400, detail="No se enviaron archivos")

    pdf_list = _load_pdf_bytes_from_paths(request.files)
    if not pdf_list:
        raise HTTPException(status_code=400, detail="Ningún archivo válido pudo leerse")

    session_id = str(uuid.uuid4())
    sessions_db[session_id] = {
        "status": "started",
        "processed": 0,
        "total": len(pdf_list),
        "total_rows": 0,
        "rows": [],
        "qa": {},
    }

    background_tasks.add_task(
        _process_real_batch,
        pdf_list,
        session_id,
        str(request.webhook_url) if request.webhook_url else None,
    )

    return UploadResponse(
        session_id=session_id,
        status="started",
        total_files=len(pdf_list),
        message="Procesamiento iniciado con el equipo de 24 agentes (pipeline real)"
    )


@app.post("/api/v1/cotizaciones/upload-files", response_model=UploadResponse)
async def upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    webhook_url: Optional[str] = Form(None),
):
    """Endpoint recomendado: acepta multipart/form-data con archivos PDF reales."""
    if not files:
        raise HTTPException(status_code=400, detail="No se recibieron archivos")

    pdf_list = []
    temp_dir = tempfile.mkdtemp(prefix="api_upload_")
    try:
        for uf in files:
            if not uf.filename.lower().endswith(".pdf"):
                continue
            content = await uf.read()
            pdf_list.append({"name": uf.filename, "bytes": content})
    finally:
        # Los bytes ya están en memoria; podemos limpiar el temp si lo usamos
        shutil.rmtree(temp_dir, ignore_errors=True)

    if not pdf_list:
        raise HTTPException(status_code=400, detail="No se recibieron PDFs válidos")

    session_id = str(uuid.uuid4())
    sessions_db[session_id] = {
        "status": "started",
        "processed": 0,
        "total": len(pdf_list),
        "total_rows": 0,
        "rows": [],
        "qa": {},
    }

    background_tasks.add_task(_process_real_batch, pdf_list, session_id, webhook_url)

    return UploadResponse(
        session_id=session_id,
        status="started",
        total_files=len(pdf_list),
        message="Procesamiento real iniciado (24 agentes + extracción Grok-style)"
    )


@app.get("/api/v1/cotizaciones/{session_id}/status", response_model=StatusResponse)
async def get_status(session_id: str):
    if session_id not in sessions_db:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")

    s = sessions_db[session_id]
    percentage = (s.get("processed", 0) / s.get("total", 1) * 100) if s.get("total") else 0

    return StatusResponse(
        session_id=session_id,
        status=s.get("status", "unknown"),
        processed=s.get("processed", 0),
        total=s.get("total", 0),
        percentage=round(percentage, 1),
        qa_summary=s.get("qa"),
    )


@app.get("/api/v1/cotizaciones/{session_id}/resultados", response_model=ResultResponse)
async def get_results(session_id: str):
    if session_id not in sessions_db:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    s = sessions_db[session_id]
    if s.get("status") != "completed":
        raise HTTPException(status_code=409, detail=f"La sesión aún no terminó (estado: {s.get('status')})")

    rows = s.get("rows", [])
    return ResultResponse(
        session_id=session_id,
        total_rows=len(rows),
        columns=s.get("columns") or (list(rows[0].keys()) if rows else []),
        sample=rows[:20],
        qa=s.get("qa", {}),
    )


# ===================== NEW SCALABLE JOB ENDPOINTS =====================

@app.post("/api/v1/jobs", tags=["jobs"])
async def create_job_from_upload(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    llm_mode: str = Form("fallback"),
    batch_size: int = Form(50),
    notify_email: Optional[str] = Form(None),
    webhook_url: Optional[str] = Form(None),
):
    """Create a real Job (persisted). PDFs go to object storage. Workers will process."""
    if not files:
        raise HTTPException(400, "No files")

    pdf_list = []
    for uf in files:
        if not uf.filename.lower().endswith(".pdf"):
            continue
        content = await uf.read()
        pdf_list.append({"name": uf.filename, "bytes": content})

    if not pdf_list:
        raise HTTPException(400, "No valid PDFs")

    job = job_mgr.create_upload_job(
        pdf_list,
        llm_mode=llm_mode,
        batch_size=batch_size,
        notify_email=notify_email,
        webhook_url=webhook_url,
    )
    # Optionally auto-enqueue a first batch (the worker will keep advancing it)
    # For demo we can start background processing here too:
    background_tasks.add_task(job_mgr.process_job_small_batch, job.id, max_files=batch_size)

    return {
        "job_id": job.id,
        "status": job.status,
        "total_files": job.total_files,
        "llm_mode": job.llm_mode,
        "message": "Job created. Use /jobs/{id}/status or run the worker to process.",
        "storage_prefix": job.storage_prefix,
    }


@app.get("/api/v1/jobs/{job_id}/status", tags=["jobs"])
async def get_job_status(job_id: str):
    from core.db import get_job
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "job_id": job.id,
        "status": job.status,
        "progress_pct": job.progress_pct,
        "processed_files": job.processed_files,
        "total_files": job.total_files,
        "total_rows": job.total_rows,
        "llm_mode": job.llm_mode,
        "source_type": job.source_type,
    }


@app.post("/api/v1/jobs/ingest-email", tags=["jobs", "email"])
async def ingest_email_job(
    query: str = Form("has:attachment filename:pdf"),
    max_messages: int = Form(100),
    llm_mode: str = Form("fallback"),
    notify_email: Optional[str] = Form(None),
):
    """Create a Job by ingesting PDFs from Gmail (real, paginated)."""
    from core.email_ingest import ingest_gmail_to_job
    job = ingest_gmail_to_job(
        query=query,
        max_messages=max_messages,
        llm_mode=llm_mode,
        notify_email=notify_email,
    )
    # Kick off first batch
    job_mgr.process_job_small_batch(job.id, max_files=30)
    return {"job_id": job.id, "status": job.status, "message": "Email ingest job created and first batch started."}


@app.get("/api/v1/jobs", tags=["jobs"])
async def list_recent_jobs(limit: int = 20):
    from core.db import list_jobs
    jobs = list_jobs(limit=limit)
    return [
        {
            "id": j.id,
            "status": j.status,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "total_files": j.total_files,
            "processed_files": j.processed_files,
            "total_rows": j.total_rows,
            "llm_mode": j.llm_mode,
            "source_type": j.source_type,
        }
        for j in jobs
    ]


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "agents": 24,
        "engine": "real-pipeline + JobManager",
        "db": "sqlite or DATABASE_URL",
        "storage": "local (or minio)",
    }
