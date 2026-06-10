import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from core.document_parser import DocumentParser
from core.llm_orchestrator import LLMOrchestrator
from .metadata_extractor import MetadataExtractor
from .table_extractor import TableExtractor

CSV_COLUMNS = [
    "Cód. Item Archivo",
    "Cód. Cotización Archivo",
    "Proveedor",
    "Descripción del Producto",
    "Cantidad",
    "Precio Unitario",
    "Precio Total",
    "NIT",
    "Moneda",
    "Tiempo Entrega",
    "Forma Pago",
    "Vigencia",
    "Comercial",
    "Correo",
    "Teléfono",
    "Archivo",
    "Página",
    "Confianza",
    "Estado",
    "Fuente",
]


class PDFExtractionPipeline:
    GROK_PROMPT = """
Extrae TODOS Y CADA UNO de los productos o servicios de este texto de cotización.
Genera una fila por cada ítem de tabla o línea de producto. No omitas ninguno.
Repite en cada fila los metadatos del proveedor (NIT, moneda, contacto, condiciones).
Si un dato no aparece, usa "NO ESPECIFICADO".

Retorna UNICAMENTE JSON válido:
{
  "proveedor": "nombre del emisor",
  "nit": "...",
  "moneda": "COP|USD|EUR",
  "tiempo_entrega": "...",
  "forma_pago": "...",
  "vigencia": "...",
  "comercial": "...",
  "correo": "...",
  "telefono": "...",
  "items": [
    {
      "descripcion": "texto exacto del producto",
      "cantidad": "1",
      "precio_unitario": "...",
      "precio_total": "..."
    }
  ]
}
"""

    def __init__(self, use_llm: bool = True, llm_mode: str | None = None):
        """
        use_llm: legacy boolean.
        llm_mode: 'none' | 'fallback' | 'always'  (preferred for jobs).
                    - none: never call LLM (pure table + markitdown + OCR)
                    - fallback: call only when table_extractor returns very few rows (current smart default)
                    - always: force LLM on every page (expensive, for difficult docs)
        """
        self.parser = DocumentParser()
        self.metadata = MetadataExtractor()
        self.tables = TableExtractor()

        effective_use_llm = use_llm
        if llm_mode:
            mode = str(llm_mode).lower()
            if mode == "none":
                effective_use_llm = False
            elif mode == "always":
                effective_use_llm = True
            # fallback keeps the conditional below

        self._llm_mode = llm_mode or ("always" if effective_use_llm else "fallback")
        self.orchestrator = LLMOrchestrator() if effective_use_llm and os.getenv("GEMINI_API_KEY") else None

    def parse_filename_codes(self, filename: str) -> tuple:
        m_item = re.search(r"Item[_\s]*(\d+(?:\.\d+)?)", filename, re.I)
        m_cot = re.search(r"Cotizaci[oó]n[_\s]*(\d+)", filename, re.I)
        item = m_item.group(1) if m_item else "NO ESPECIFICADO"
        cot = m_cot.group(1) if m_cot else "1"
        return item, cot

    def process_pdf_bytes(
        self,
        filename: str,
        pdf_bytes: bytes,
        on_progress: Optional[Callable[[str, str], None]] = None,
    ) -> List[Dict[str, Any]]:
        def log(agent_id: str, msg: str):
            if on_progress:
                on_progress(agent_id, msg)

        log("senior_dev", f"Iniciando pipeline para {filename}")
        item_code, cot_code = self.parse_filename_codes(filename)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(pdf_bytes)
            tmp_path = tmp.name

        try:
            log("pdf_analyst", "Clasificando documento y extrayendo páginas")
            pages = self.parser.parse_document_by_pages(tmp_path)
            full_text = "\n".join(p["text"] for p in pages if p.get("text"))

            log("metadata_extractor", "Extrayendo metadatos de contacto y condiciones")
            meta = self.metadata.extract(full_text, filename)

            log("table_analyst", "Parseando tablas con pdfplumber")
            table_items = self.tables.extract_from_pdf(tmp_path)

            llm_items = []
            llm_meta = {}
            force_llm = (getattr(self, "_llm_mode", "fallback") == "always")
            skip_llm = (getattr(self, "_llm_mode", "fallback") == "none") or (os.getenv("AUDITOR_LLM_MODE", "").lower() == "none")

            use_llm_for_this = self.orchestrator and not skip_llm and (force_llm or (not table_items or len(table_items) < 3))

            if use_llm_for_this:
                log("ml_engineer", "Activando extracción IA (Grok-style) por página (llm_mode=%s)" % getattr(self, "_llm_mode", "fallback"))
                for p in pages:
                    if not p.get("text", "").strip():
                        continue
                    result = self.orchestrator.process_document(
                        p["text"], p.get("is_difficult", False), self.GROK_PROMPT
                    )
                    data = result.get("data", {})
                    if isinstance(data, dict):
                        llm_meta.update({k: v for k, v in data.items() if v})
                        for it in data.get("items", []) or []:
                            llm_items.append({**it, "_page": p.get("page", 1), "_confidence": result.get("confidence", "LOW")})

            merged_meta = self._merge_meta(meta, llm_meta)
            raw_items = table_items or self._llm_items_to_rows(llm_items)

            if not raw_items:
                log("procurement_analyst", "Sin ítems detectados — generando fila de ficha técnica")
                raw_items = [{
                    "Descripción del Producto": "Documento sin tabla de precios detectada (ficha técnica o catálogo)",
                    "Cantidad": "1",
                    "Precio Unitario": "NO ESPECIFICADO",
                    "Precio Total": "NO ESPECIFICADO",
                    "_page": 1,
                    "_confidence": "LOW",
                }]

            log("data_engineer", f"Consolidando {len(raw_items)} filas")
            rows = []
            for it in raw_items:
                row = self._build_row(item_code, cot_code, filename, merged_meta, it)
                rows.append(row)

            log("data_validator", f"Validadas {len(rows)} filas")
            return rows

        except Exception as exc:
            # Corrupt / unreadable shard handling - never kill the whole job
            log("security", f"SHARD CORRUPTO o falló extracción: {filename} - {str(exc)[:200]}")
            # Return a single error row so the job can continue and we have traceability
            return [{
                "Cód. Item Archivo": item_code,
                "Cód. Cotización Archivo": cot_code,
                "Proveedor": "ERROR_LECTURA",
                "Descripción del Producto": f"[SHARD CORRUPTO] {filename} - {str(exc)[:150]}",
                "Cantidad": "0",
                "Precio Unitario": "NO ESPECIFICADO",
                "Precio Total": "NO ESPECIFICADO",
                "NIT": "NO ESPECIFICADO",
                "Moneda": "COP",
                "Tiempo Entrega": "NO ESPECIFICADO",
                "Forma Pago": "NO ESPECIFICADO",
                "Vigencia": "NO ESPECIFICADO",
                "Comercial": "NO ESPECIFICADO",
                "Correo": "NO ESPECIFICADO",
                "Teléfono": "NO ESPECIFICADO",
                "Archivo": filename,
                "Página": 0,
                "Confianza": "FAILED",
                "Estado": "❌ Corrupto / Error lectura",
                "Fuente": "error_handler",
            }]
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    def _merge_meta(self, regex_meta: Dict, llm_meta: Dict) -> Dict:
        out = dict(regex_meta)
        mapping = {
            "proveedor": "Proveedor",
            "nit": "NIT",
            "moneda": "Moneda",
            "tiempo_entrega": "Tiempo Entrega",
            "forma_pago": "Forma Pago",
            "vigencia": "Vigencia",
            "comercial": "Comercial",
            "correo": "Correo",
            "telefono": "Teléfono",
        }
        for src, dst in mapping.items():
            val = llm_meta.get(src)
            if val and str(val).strip() and out.get(dst) in (None, "", "NO ESPECIFICADO"):
                out[dst] = str(val).strip()
        return out

    def _llm_items_to_rows(self, llm_items: List[Dict]) -> List[Dict]:
        rows = []
        for it in llm_items:
            rows.append({
                "Descripción del Producto": it.get("descripcion") or it.get("Descripción del Producto") or "NO ESPECIFICADO",
                "Cantidad": str(it.get("cantidad", "1")),
                "Precio Unitario": str(it.get("precio_unitario", it.get("Precio Unitario", "NO ESPECIFICADO"))),
                "Precio Total": str(it.get("precio_total", it.get("Precio Total", "NO ESPECIFICADO"))),
                "_page": it.get("_page", 1),
                "_confidence": it.get("_confidence", "MEDIUM"),
            })
        return rows

    def _build_row(self, item_code: str, cot_code: str, filename: str, meta: Dict, item: Dict) -> Dict[str, Any]:
        conf = item.get("_confidence", "HIGH")
        return {
            "Cód. Item Archivo": item_code,
            "Cód. Cotización Archivo": cot_code,
            "Proveedor": meta.get("Proveedor", "NO ESPECIFICADO"),
            "Descripción del Producto": item.get("Descripción del Producto", "NO ESPECIFICADO"),
            "Cantidad": item.get("Cantidad", "1"),
            "Precio Unitario": item.get("Precio Unitario", "NO ESPECIFICADO"),
            "Precio Total": item.get("Precio Total", "NO ESPECIFICADO"),
            "NIT": meta.get("NIT", "NO ESPECIFICADO"),
            "Moneda": meta.get("Moneda", "COP"),
            "Tiempo Entrega": meta.get("Tiempo Entrega", "NO ESPECIFICADO"),
            "Forma Pago": meta.get("Forma Pago", "NO ESPECIFICADO"),
            "Vigencia": meta.get("Vigencia", "NO ESPECIFICADO"),
            "Comercial": meta.get("Comercial", "NO ESPECIFICADO"),
            "Correo": meta.get("Correo", "NO ESPECIFICADO"),
            "Teléfono": meta.get("Teléfono", "NO ESPECIFICADO"),
            "Archivo": filename,
            "Página": item.get("_page", 1),
            "Confianza": conf,
            "Estado": "✅ Completado",
            "Fuente": "tabla+ia" if self.orchestrator else "tabla",
        }