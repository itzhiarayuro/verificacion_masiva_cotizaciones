import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai no está instalado.")

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("openai no está instalado (requerido para NVIDIA NIM).")

class LLMOrchestrator:
    def __init__(self):
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.nvidia_api_key = os.getenv("NVIDIA_API_KEY")

        if self.gemini_api_key and GEMINI_AVAILABLE:
            genai.configure(api_key=self.gemini_api_key)
            self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
        else:
            self.gemini_model = None

        if self.nvidia_api_key and OPENAI_AVAILABLE:
            self.nvidia_client = OpenAI(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=self.nvidia_api_key
            )
        else:
            self.nvidia_client = None

    def _extract_with_gemini(self, text: str, prompt_instrucciones: str) -> Dict[str, Any]:
        """Extrae la información usando Gemini (Primary)."""
        if not self.gemini_model:
            return {"error": "Gemini no configurado", "confidence": "LOW"}

        full_prompt = f"""
        Instrucciones: {prompt_instrucciones}

        Texto del documento:
        {text}

        Retorna UNICAMENTE un JSON válido con los campos solicitados. Si no encuentras un dato, pon null.
        """

        try:
            response = self.gemini_model.generate_content(full_prompt)
            # Limpiar posible formato markdown del JSON
            response_text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(response_text)
            
            # Evaluar confianza: Si todo es null, la confianza es baja.
            is_empty = all(v is None for v in data.values())
            confidence = "LOW" if is_empty else "HIGH"

            return {
                "data": data,
                "confidence": confidence,
                "source": "gemini"
            }
        except Exception as e:
            logger.error(f"Error en Gemini: {e}")
            return {"error": str(e), "confidence": "LOW"}

    def _review_with_nvidia(self, text: str, prompt_instrucciones: str, gemini_data: Dict[str, Any]) -> Dict[str, Any]:
        """Revisa la extracción con NVIDIA si la confianza fue baja."""
        if not self.nvidia_client:
            return {"error": "NVIDIA no configurado", "confidence": "LOW"}

        full_prompt = f"""
        Eres un auditor revisando una extracción de datos.
        Instrucciones originales: {prompt_instrucciones}
        
        Extracción previa (Gemini): {json.dumps(gemini_data)}
        
        Texto del documento:
        {text}
        
        Si la extracción previa tiene datos en null, intenta encontrarlos en el texto.
        Retorna UNICAMENTE un JSON válido con los datos finales corregidos.
        """

        try:
            completion = self.nvidia_client.chat.completions.create(
                model="meta/llama-3.1-70b-instruct",
                messages=[{"role": "user", "content": full_prompt}],
                temperature=0.2,
                top_p=0.7,
                max_tokens=1024,
            )
            response_text = completion.choices[0].message.content.replace("```json", "").replace("```", "").strip()
            data = json.loads(response_text)
            
            return {
                "data": data,
                "confidence": "MEDIUM",  # Medium porque requirió segunda opinión
                "source": "nvidia"
            }
        except Exception as e:
            logger.error(f"Error en NVIDIA: {e}")
            return {"error": str(e), "confidence": "LOW"}

    def process_document(self, text: str, is_difficult: bool, prompt_instrucciones: str) -> Dict[str, Any]:
        """
        Orquesta el flujo. Primero Gemini, si falla o es un doc difícil, pasa a NVIDIA.
        """
        if not text.strip():
            return {"status": "error", "message": "Texto vacío", "confidence": "NONE"}

        gemini_result = self._extract_with_gemini(text, prompt_instrucciones)
        
        # Si Gemini falló, trajo nulls (LOW) o el documento ya venía marcado como difícil (ej. OCR)
        if gemini_result.get("confidence") == "LOW" or is_difficult:
            logger.info("Activando revisión con NVIDIA...")
            nvidia_result = self._review_with_nvidia(text, prompt_instrucciones, gemini_result.get("data", {}))
            
            if "error" not in nvidia_result:
                return nvidia_result

        return gemini_result
