import json
import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, session_path: str = "outputs/session_state.json"):
        self.session_path = session_path
        self.state = {
            "session_id": "",
            "files_to_process": [],
            "processed_results": [],
            "current_index": 0,
            "status": "idle" # idle, running, paused, completed
        }
        self.load_session()

    def load_session(self) -> bool:
        """Carga la sesión previa si existe."""
        if os.path.exists(self.session_path):
            try:
                with open(self.session_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Validación básica
                    if "processed_results" in data:
                        self.state = data
                        return True
            except Exception as e:
                logger.error(f"Error al cargar sesión: {e}")
        return False

    def save_session(self):
        """Guarda el estado actual de la sesión en disco (Checkpoint)."""
        os.makedirs(os.path.dirname(self.session_path), exist_ok=True)
        try:
            with open(self.session_path, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=4)
        except Exception as e:
            logger.error(f"Error al guardar sesión: {e}")

    def start_new_session(self, session_id: str, files: List[str]):
        """Inicializa una nueva sesión destruyendo la anterior."""
        self.state = {
            "session_id": session_id,
            "files_to_process": files,
            "processed_results": [],
            "current_index": 0,
            "status": "running"
        }
        self.save_session()

    def add_result(self, file_path: str, result_data: Dict[str, Any]):
        """Añade el resultado de un documento y hace checkpoint."""
        self.state["processed_results"].append({
            "file": file_path,
            "result": result_data
        })
        self.state["current_index"] += 1
        self.save_session()

    def mark_completed(self):
        """Marca la sesión como completada."""
        self.state["status"] = "completed"
        self.save_session()

    def clear_session(self):
        """Borra el archivo de sesión una vez todo ha sido exportado exitosamente."""
        if os.path.exists(self.session_path):
            os.remove(self.session_path)
        self.state = {
            "session_id": "",
            "files_to_process": [],
            "processed_results": [],
            "current_index": 0,
            "status": "idle"
        }
