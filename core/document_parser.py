import os
from pathlib import Path
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

try:
    from markitdown import MarkItDown
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False
    logger.warning("markitdown no está instalado.")

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logger.warning("pdfplumber no está instalado.")

try:
    import pytesseract
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logger.warning("pytesseract o pdf2image no instalados. OCR no disponible.")

class DocumentParser:
    """
    Parsea documentos PDF usando una estrategia de cascada:
    1. MarkItDown (Preferido, reduce tokens)
    2. pdfplumber (Fallback para tablas y layout)
    3. OCR (Último recurso para imágenes escaneadas)
    """

    def parse_document(self, file_path: str) -> Dict[str, Any]:
        """
        Retorna un diccionario con:
        - text: Texto extraído
        - method: Método utilizado ('markitdown', 'pdfplumber', 'ocr', 'failed')
        - is_difficult: True si se usó OCR o si extrajo muy poco texto
        """
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return {"text": "", "method": "failed", "is_difficult": True}

        # 1. MarkItDown
        if MARKITDOWN_AVAILABLE:
            try:
                md = MarkItDown()
                result = md.convert(file_path)
                text = result.text_content
                if text and len(text.strip()) > 100:
                    return {
                        "text": text,
                        "method": "markitdown",
                        "is_difficult": False
                    }
            except Exception as e:
                logger.warning(f"MarkItDown falló para {file_path}: {e}")

        # 2. pdfplumber
        if PDFPLUMBER_AVAILABLE and file_path.lower().endswith('.pdf'):
            try:
                text = ""
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        extracted = page.extract_text()
                        if extracted:
                            text += extracted + "\n"
                
                if text and len(text.strip()) > 100:
                    return {
                        "text": text,
                        "method": "pdfplumber",
                        "is_difficult": False
                    }
            except Exception as e:
                logger.warning(f"pdfplumber falló para {file_path}: {e}")

        # 3. OCR (pytesseract)
        if OCR_AVAILABLE and file_path.lower().endswith('.pdf'):
            try:
                images = convert_from_path(file_path)
                text = ""
                for img in images:
                    text += pytesseract.image_to_string(img) + "\n"
                
                if text and len(text.strip()) > 50:
                    return {
                        "text": text,
                        "method": "ocr",
                        "is_difficult": True  # OCR siempre se marca como difícil
                    }
            except Exception as e:
                logger.warning(f"OCR falló para {file_path}: {e}")

        # Fallo absoluto
        return {
            "text": "",
            "method": "failed",
            "is_difficult": True
        }
