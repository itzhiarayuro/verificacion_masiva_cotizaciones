import re
from typing import Any, Dict, List

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False


class TableExtractor:
    NO = "NO ESPECIFICADO"

    def extract_from_pdf(self, file_path: str) -> List[Dict[str, str]]:
        if not PDFPLUMBER_AVAILABLE:
            return []
        items: List[Dict[str, str]] = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables() or []
                    for table in tables:
                        items.extend(self._parse_table(table))
                    text = page.extract_text() or ""
                    items.extend(self._parse_text_lines(text))
        except Exception:
            return items
        return self._dedupe(items)

    def _parse_table(self, table: List[List[Any]]) -> List[Dict[str, str]]:
        if not table or len(table) < 2:
            return []
        header = [str(c or "").lower() for c in table[0]]
        desc_idx = self._find_col(header, ["descrip", "producto", "material", "concepto", "detalle"])
        qty_idx = self._find_col(header, ["cant", "qty", "unid"])
        unit_idx = self._find_col(header, ["unit", "p.unit", "precio unit", "v.unit", "valor unit"])
        total_idx = self._find_col(header, ["total", "v.total", "valor total", "importe"])

        rows = []
        for row in table[1:]:
            if not row or not any(row):
                continue
            desc = self._cell(row, desc_idx) or self._cell(row, 0)
            if not desc or len(desc) < 3:
                continue
            if self._is_header_row(desc):
                continue
            rows.append({
                "Descripción del Producto": desc,
                "Cantidad": self._cell(row, qty_idx) or "1",
                "Precio Unitario": self._cell(row, unit_idx) or self.NO,
                "Precio Total": self._cell(row, total_idx) or self.NO,
            })
        return rows

    def _parse_text_lines(self, text: str) -> List[Dict[str, str]]:
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if len(line) < 10:
                continue
            m = re.match(
                r"^(.{10,120}?)\s+(\d+(?:[.,]\d+)?)\s+([\d.,]+)\s+([\d.,]+)\s*$",
                line,
            )
            if m:
                rows.append({
                    "Descripción del Producto": m.group(1).strip(),
                    "Cantidad": m.group(2),
                    "Precio Unitario": m.group(3),
                    "Precio Total": m.group(4),
                })
        return rows

    def _find_col(self, header: List[str], keys: List[str]) -> int:
        for i, h in enumerate(header):
            if any(k in h for k in keys):
                return i
        return -1

    def _cell(self, row: List[Any], idx: int) -> str:
        if idx < 0 or idx >= len(row):
            return ""
        return str(row[idx] or "").strip()

    def _is_header_row(self, desc: str) -> bool:
        low = desc.lower()
        return any(w in low for w in ("descrip", "producto", "cantidad", "precio", "total", "subtotal"))

    def _dedupe(self, items: List[Dict[str, str]]) -> List[Dict[str, str]]:
        seen = set()
        out = []
        for it in items:
            key = (it.get("Descripción del Producto", ""), it.get("Precio Unitario", ""))
            if key in seen:
                continue
            seen.add(key)
            out.append(it)
        return out