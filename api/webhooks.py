import requests
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def send_webhook(url: str, payload: Dict[str, Any]):
    """Envía un POST request al ERP/CRM cuando el proceso termina."""
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"Webhook enviado exitosamente a {url}")
    except Exception as e:
        logger.error(f"Fallo al enviar webhook a {url}: {e}")
