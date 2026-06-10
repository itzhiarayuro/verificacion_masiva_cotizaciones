from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any

class UploadRequest(BaseModel):
    """Fallback JSON mode (paths on server disk). Prefer the multipart /upload endpoint."""
    files: List[str]  # Rutas a los archivos (el servidor debe poder leerlos)
    excel_template: Optional[str] = "obra_civil"
    webhook_url: Optional[HttpUrl] = None


class UploadResponse(BaseModel):
    session_id: str
    status: str
    total_files: int
    message: str


class StatusResponse(BaseModel):
    session_id: str
    status: str
    processed: int
    total: int
    percentage: float
    qa_summary: Optional[Dict[str, Any]] = None


class ResultResponse(BaseModel):
    session_id: str
    total_rows: int
    columns: List[str]
    sample: List[Dict[str, Any]]
    qa: Dict[str, Any]


class WebhookPayload(BaseModel):
    session_id: str
    status: str
    results_url: str
    data: List[Dict[str, Any]]
