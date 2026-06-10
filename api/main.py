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

app = FastAPI(
    title="Auditor de Cotizaciones API - Real",
    description="API REST que usa el mismo orquestador de 24 agentes + pipeline Grok-style que la UI",
    version="3.1.0"
)

# In-memory session store (for demo; in prod use Redis/DB)
sessions_db = {}
logger = logging.getLogger(__name__)


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


@app.get("/health")
async def health():
    return {"status": "ok", "agents": 24, "engine": "real-pipeline"}
