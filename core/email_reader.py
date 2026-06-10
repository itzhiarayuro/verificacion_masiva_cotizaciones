import os
import base64
import logging
from typing import List, Dict, Any, Optional, Iterator
from pathlib import Path
from datetime import datetime, timedelta

# Google API
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GMAIL_AVAILABLE = True
except ImportError:
    GMAIL_AVAILABLE = False

# Microsoft API
try:
    import msal
    import requests
    OUTLOOK_AVAILABLE = True
except ImportError:
    OUTLOOK_AVAILABLE = False

logger = logging.getLogger(__name__)


class EmailReader:
    """
    Full Gmail + (future) Outlook reader for massive cotizaciones ingestion.

    - Supports pagination (page through thousands of messages).
    - Rich queries (date ranges, from:, subject:, has:attachment, etc.).
    - Downloads attachments directly into storage (or local temp).
    - Can mark messages as read / apply labels after successful processing.
    - Reuses the same token.json flow as before (desktop OAuth).

    Recommended query examples:
        "has:attachment filename:pdf newer_than:2025/01/01"
        "from:ventas@proveedor.com has:attachment filename:pdf"
        "subject:cotizacion OR subject:cotiz OR subject:proforma"
    """

    def __init__(self, download_dir: str = "outputs/temp/email_downloads"):
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)
        # We request modify so we can mark-as-read / label after ingesting
        self.gmail_scopes = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.modify",
        ]

    # ---------------- Gmail ----------------

    def authenticate_gmail(self, credentials_path: str = "credentials.json") -> Any:
        """OAuth2 desktop flow. Caches in token.json."""
        if not GMAIL_AVAILABLE:
            raise RuntimeError("Google API client libraries not installed")
        creds = None
        token_path = "token.json"

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, self.gmail_scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    creds = None
            if not creds:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, self.gmail_scopes)
                creds = flow.run_local_server(port=0)
            with open(token_path, "w") as token:
                token.write(creds.to_json())

        return build("gmail", "v1", credentials=creds)

    def list_messages(
        self,
        query: str = "has:attachment filename:pdf",
        max_results: int = 500,
        page_size: int = 50,
    ) -> Iterator[Dict[str, Any]]:
        """Yield message dicts (full get) with pagination. Much better than the old max=10."""
        if not GMAIL_AVAILABLE:
            logger.error("Gmail libs not available")
            return

        try:
            service = self.authenticate_gmail()
            page_token = None
            fetched = 0

            while fetched < max_results:
                resp = service.users().messages().list(
                    userId="me",
                    q=query,
                    maxResults=min(page_size, max_results - fetched),
                    pageToken=page_token,
                ).execute()

                messages = resp.get("messages", [])
                if not messages:
                    break

                for m in messages:
                    try:
                        full = service.users().messages().get(userId="me", id=m["id"], format="full").execute()
                        yield full
                        fetched += 1
                        if fetched >= max_results:
                            return
                    except HttpError as e:
                        logger.warning(f"Could not fetch message {m['id']}: {e}")

                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
        except Exception as e:
            logger.error(f"Error listing Gmail messages: {e}")

    def fetch_gmail_pdfs(
        self,
        query: str = "has:attachment filename:pdf",
        max_messages: int = 200,
        download_dir: Optional[str] = None,
        mark_read: bool = False,
        label_processed: Optional[str] = None,
    ) -> List[str]:
        """
        Download PDF attachments for matching messages.
        Returns list of local file paths.
        Now supports large volumes via pagination.
        """
        if not GMAIL_AVAILABLE:
            logger.error("Librerías de Google no instaladas.")
            return []

        out_dir = Path(download_dir or self.download_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        downloaded: List[str] = []
        service = self.authenticate_gmail()

        for msg in self.list_messages(query=query, max_results=max_messages):
            try:
                payload = msg.get("payload", {})
                parts = payload.get("parts", []) or [payload]  # sometimes top level has attachment

                msg_id = msg["id"]
                has_pdf = False

                for part in parts:
                    filename = (part.get("filename") or "").strip()
                    if not filename.lower().endswith(".pdf"):
                        continue
                    has_pdf = True

                    body = part.get("body", {})
                    if "data" in body:
                        data = body["data"]
                    else:
                        att_id = body.get("attachmentId")
                        if not att_id:
                            continue
                        att = service.users().messages().attachments().get(
                            userId="me", messageId=msg_id, id=att_id
                        ).execute()
                        data = att["data"]

                    file_data = base64.urlsafe_b64decode(data.encode("UTF-8"))

                    # unique name
                    safe_name = filename
                    base, ext = os.path.splitext(safe_name)
                    counter = 1
                    dest = out_dir / safe_name
                    while dest.exists():
                        dest = out_dir / f"{base}_{counter}{ext}"
                        counter += 1

                    dest.write_bytes(file_data)
                    downloaded.append(str(dest))
                    logger.info(f"Downloaded PDF attachment: {dest.name}")

                if has_pdf and mark_read:
                    # Remove UNREAD label
                    try:
                        service.users().messages().modify(
                            userId="me",
                            id=msg_id,
                            body={"removeLabelIds": ["UNREAD"]},
                        ).execute()
                    except Exception:
                        pass

                if has_pdf and label_processed:
                    try:
                        # Create label if it doesn't exist (best effort)
                        service.users().messages().modify(
                            userId="me", id=msg_id, body={"addLabelIds": [label_processed]}
                        ).execute()
                    except Exception:
                        pass

            except Exception as e:
                logger.error(f"Error processing message {msg.get('id')}: {e}")

        return downloaded

    def fetch_and_prepare_for_job(
        self,
        query: str,
        max_messages: int = 200,
        storage=None,  # optional StorageBackend to write directly
        job_prefix: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        High-level helper used by email ingestion.
        Returns list of {"name": , "bytes": , "message_id": , ...} ready for JobManager
        or writes directly to storage if provided.
        """
        local_files = self.fetch_gmail_pdfs(query=query, max_messages=max_messages)

        prepared = []
        for path in local_files:
            p = Path(path)
            entry = {"name": p.name, "path": str(p), "bytes": None}
            if storage and job_prefix:
                key = f"{job_prefix}/originals/{p.name}"
                storage.put_file(key, str(p))
                entry["storage_key"] = key
            prepared.append(entry)
        return prepared

    # ---------------- Outlook (still placeholder but better structure) ----------------

    def fetch_outlook_pdfs(self, **kwargs) -> List[str]:
        """Full Outlook/Graph implementation is TODO (needs Azure app registration + MSAL)."""
        logger.info("Outlook integration is still a stub. Provide Azure AD app + use MS Graph.")
        return []

    # ---------------- Utilities ----------------

    def build_date_query(self, days_back: int = 30, extra: str = "") -> str:
        since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y/%m/%d")
        q = f"has:attachment filename:pdf newer_than:{since}"
        if extra:
            q = f"{q} {extra}"
        return q
