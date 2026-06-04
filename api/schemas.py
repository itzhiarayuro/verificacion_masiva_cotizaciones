from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any

class UploadRequest(BaseModel):
    files: List[str]  # Rutas a los archivos
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

class WebhookPayload(BaseModel):
    session_id: str
    status: str
    results_url: str
    data: List[Dict[str, Any]]
