import hashlib
from typing import List, Dict, Any

class Validator:
    """Ejecuta reglas de negocio y detección de fraude/errores sobre los documentos."""

    def __init__(self):
        self.seen_hashes = {}

    def compute_file_hash(self, file_path: str) -> str:
        """Genera SHA-256 del archivo para detectar duplicados exactos."""
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                buf = f.read(65536)
                while len(buf) > 0:
                    hasher.update(buf)
                    buf = f.read(65536)
            return hasher.hexdigest()
        except Exception:
            return ""

    def validate_duplicate_file(self, file_path: str) -> bool:
        """Retorna True si el archivo ya fue procesado antes (duplicado exacto)."""
        file_hash = self.compute_file_hash(file_path)
        if not file_hash:
            return False
            
        if file_hash in self.seen_hashes:
            return True
            
        self.seen_hashes[file_hash] = file_path
        return False
