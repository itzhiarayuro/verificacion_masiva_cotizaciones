"""
EmailSender: send notifications, result summaries, alerts.

Primary: reuse Gmail API (same credentials as reader).
Fallback: SMTP (for non-Gmail or when you prefer).

After a job finishes you can do:
    sender.send_job_summary(job, to=job.notify_email, attach_small_excel=True)
"""
from __future__ import annotations
import base64
import logging
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional

logger = logging.getLogger(__name__)

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False


class EmailSender:
    def __init__(self, credentials_path: str = "credentials.json", token_path: str = "token.json"):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.gmail_scopes = [
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.modify",  # for future label/move
        ]
        self._service = None

    def _get_gmail_service(self):
        if self._service:
            return self._service
        if not GMAIL_AVAILABLE:
            raise RuntimeError("Google API libs not installed")
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, self.gmail_scopes)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, self.gmail_scopes)
                creds = flow.run_local_server(port=0)
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())
        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def send_text(self, to: str, subject: str, body: str, from_email: str = "me") -> bool:
        """Simple plain text email."""
        if not to:
            logger.warning("No recipient for email")
            return False
        try:
            service = self._get_gmail_service()
            message = MIMEText(body, "plain", "utf-8")
            message["to"] = to
            message["from"] = from_email
            message["subject"] = subject
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
            service.users().messages().send(userId="me", body={"raw": raw}).execute()
            logger.info(f"Email sent to {to}: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return False

    def send_job_summary(
        self,
        job,
        to: Optional[str] = None,
        attach_small_excel: bool = False,
        extra_text: str = "",
    ) -> bool:
        """Send a nice summary after job completion. to= falls back to job.notify_email."""
        recipient = to or getattr(job, "notify_email", None)
        if not recipient:
            return False

        subject = f"[Auditor Cotizaciones] Job {job.id[:8]} terminado — {job.total_rows} filas de {job.total_files} PDFs"
        body = f"""Hola,

El procesamiento del lote ha finalizado.

Job ID: {job.id}
Estado: {job.status}
Archivos: {job.processed_files}/{job.total_files}
Filas extraídas: {job.total_rows}
LLM mode usado: {job.llm_mode}
Progreso: {job.progress_pct}%

Resultados disponibles en storage:
  Prefijo: {job.storage_prefix or 'N/A'}
  (busca los .parquet y .csv en la carpeta de resultados)

{extra_text}

Saludos,
Auditor de Cotizaciones (equipo de 24 agentes)
"""
        return self.send_text(recipient, subject, body)

    # You can extend with HTML + attachments (small preview Excel) using MIMEMultipart + openpyxl in memory.
