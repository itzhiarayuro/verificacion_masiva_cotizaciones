from fastapi import FastAPI, BackgroundTasks, HTTPException
import uuid
import os
import logging
from .schemas import UploadRequest, UploadResponse, StatusResponse, WebhookPayload
from .webhooks import send_webhook

app = FastAPI(
    title="Auditor de Cotizaciones API",
    description="API REST para integración con ERPs y CRMs",
    version="3.0.0"
)

# Simulated in-memory store for sessions (In production, use SQLite/Redis)
sessions_db = {}
logger = logging.getLogger(__name__)

def process_files_background(session_id: str, files: list, webhook_url: str):
    """Procesamiento en background (Simulado para la API)."""
    # Aquí se llamaría al orquestador LLM real
    sessions_db[session_id] = {
        "status": "processing",
        "processed": 0,
        "total": len(files)
    }
    
    # ... Simulación de procesamiento ...
    sessions_db[session_id]["processed"] = len(files)
    sessions_db[session_id]["status"] = "completed"
    
    if webhook_url:
        payload = WebhookPayload(
            session_id=session_id,
            status="completed",
            results_url=f"/api/v1/cotizaciones/{session_id}/resultados",
            data=[]
        )
        send_webhook(webhook_url, payload.dict())

@app.post("/api/v1/cotizaciones/upload", response_model=UploadResponse)
async def upload_cotizaciones(request: UploadRequest, background_tasks: BackgroundTasks):
    if not request.files:
        raise HTTPException(status_code=400, detail="No se enviaron archivos")
    
    session_id = str(uuid.uuid4())
    background_tasks.add_task(process_files_background, session_id, request.files, request.webhook_url)
    
    return UploadResponse(
        session_id=session_id,
        status="started",
        total_files=len(request.files),
        message="Procesamiento iniciado en background"
    )

@app.get("/api/v1/cotizaciones/{session_id}/status", response_model=StatusResponse)
async def get_status(session_id: str):
    if session_id not in sessions_db:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
        
    session = sessions_db[session_id]
    percentage = (session["processed"] / session["total"]) * 100 if session["total"] > 0 else 0
    
    return StatusResponse(
        session_id=session_id,
        status=session["status"],
        processed=session["processed"],
        total=session["total"],
        percentage=percentage
    )
