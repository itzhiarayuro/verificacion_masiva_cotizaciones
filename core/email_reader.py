import os
import base64
import logging
from typing import List, Dict, Any
from pathlib import Path

# Google API
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
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
    def __init__(self, download_dir: str = "outputs/temp/email_downloads"):
        self.download_dir = download_dir
        os.makedirs(self.download_dir, exist_ok=True)
        self.gmail_scopes = ['https://www.googleapis.com/auth/gmail.readonly']

    def authenticate_gmail(self, credentials_path: str = 'credentials.json') -> Any:
        """Autenticación OAuth2 para Gmail."""
        creds = None
        token_path = 'token.json'
        
        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, self.gmail_scopes)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, self.gmail_scopes)
                creds = flow.run_local_server(port=0)
            
            with open(token_path, 'w') as token:
                token.write(creds.to_json())
                
        return build('gmail', 'v1', credentials=creds)

    def fetch_gmail_pdfs(self, query: str = "has:attachment filename:pdf") -> List[str]:
        """Busca correos en Gmail y descarga los PDFs adjuntos."""
        if not GMAIL_AVAILABLE:
            logger.error("Librerías de Google no instaladas.")
            return []

        downloaded_files = []
        try:
            service = self.authenticate_gmail()
            results = service.users().messages().list(userId='me', q=query, maxResults=10).execute()
            messages = results.get('messages', [])

            for msg in messages:
                msg_id = msg['id']
                message = service.users().messages().get(userId='me', id=msg_id).execute()
                parts = message.get('payload', {}).get('parts', [])
                
                for part in parts:
                    if part.get('filename') and part.get('filename').lower().endswith('.pdf'):
                        if 'data' in part['body']:
                            data = part['body']['data']
                        else:
                            att_id = part['body']['attachmentId']
                            att = service.users().messages().attachments().get(userId='me', messageId=msg_id, id=att_id).execute()
                            data = att['data']
                        
                        file_data = base64.urlsafe_b64decode(data.encode('UTF-8'))
                        file_path = os.path.join(self.download_dir, part['filename'])
                        
                        # Evitar sobreescribir si hay nombres repetidos
                        base, ext = os.path.splitext(file_path)
                        counter = 1
                        while os.path.exists(file_path):
                            file_path = f"{base}_{counter}{ext}"
                            counter += 1
                            
                        with open(file_path, 'wb') as f:
                            f.write(file_data)
                        downloaded_files.append(file_path)
                        
            return downloaded_files
        except Exception as e:
            logger.error(f"Error descargando correos de Gmail: {e}")
            return []

    # Se puede agregar lógica similar para Outlook usando MSAL y Microsoft Graph API.
    def fetch_outlook_pdfs(self) -> List[str]:
        """Placeholder para la integración con Outlook."""
        logger.info("Integración con Outlook requiere configuración en Azure AD.")
        return []
