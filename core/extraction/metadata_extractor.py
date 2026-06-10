import re
from typing import Dict


class MetadataExtractor:
    NO = "NO ESPECIFICADO"

    def extract(self, text: str, filename: str = "") -> Dict[str, str]:
        t = text or ""
        upper = t.upper()

        proveedor = self._extract_proveedor(t, filename)
        return {
            "Proveedor": proveedor,
            "NIT": self._first_match(t, [
                r"NIT[:\s]*([\d.\-]+)",
                r"Nit[:\s]*([\d.\-]+)",
                r"Identificaci[oó]n\s+tributaria[:\s]*([\d.\-]+)",
            ]) or self.NO,
            "Moneda": "USD" if re.search(r"\bUSD\b", upper) else ("EUR" if re.search(r"\bEUR\b", upper) else "COP"),
            "Tiempo Entrega": self._first_match(t, [
                r"(?i)(?:tiempo|plazo)\s+de\s+entrega[:\s]*([^\n]{3,80})",
                r"(?i)entrega[:\s]*(\d+\s*(?:d[ií]as?|semanas?)[^\n]*)",
                r"(?i)(\d+\s*[-–]\s*\d+\s*semanas?)",
            ]) or self.NO,
            "Forma Pago": self._first_match(t, [
                r"(?i)forma\s+de\s+pago[:\s]*([^\n]{3,80})",
                r"(?i)condiciones?\s+de\s+pago[:\s]*([^\n]{3,80})",
                r"(?i)(\d+\s*%\s*anticipo[^\n]*)",
            ]) or self.NO,
            "Vigencia": self._first_match(t, [
                r"(?i)vigencia[:\s]*([^\n]{3,60})",
                r"(?i)validez\s+de\s+la\s+oferta[:\s]*([^\n]{3,60})",
                r"(?i)(\d+\s*d[ií]as?\s+calendario)",
            ]) or self.NO,
            "Comercial": self._first_match(t, [
                r"(?i)(?:asesor|comercial|vendedor|elaborado\s+por|contacto)[:\s]*([A-ZÁÉÍÓÚÑ][^\n]{2,50})",
                r"(?i)Ing\.?\s+([A-ZÁÉÍÓÚÑ][^\n]{2,40})",
            ]) or self.NO,
            "Correo": self._first_match(t, [
                r"([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
            ]) or self.NO,
            "Teléfono": self._first_match(t, [
                r"(\+?\d{1,3}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4})",
                r"(3\d{2}[\s\-]?\d{3}[\s\-]?\d{4})",
            ]) or self.NO,
        }

    def _first_match(self, text: str, patterns: list) -> str:
        for pat in patterns:
            m = re.search(pat, text)
            if m:
                val = m.group(1).strip()
                if len(val) > 2:
                    return val
        return ""

    def _extract_proveedor(self, text: str, filename: str) -> str:
        if filename:
            parts = filename.replace(".pdf", "").replace(".PDF", "").split("_")
            if len(parts) >= 5:
                return " ".join(parts[4:]).replace("-", " ").strip() or self.NO
            if len(parts) >= 1:
                last = parts[-1]
                if last.lower() not in ("pdf", "cotizacion", "item") and not last.isdigit():
                    return last.replace("-", " ").strip()

        m = re.search(r"(?i)(?:empresa|proveedor|de)[:\s]*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s&.\-]{3,60})", text)
        if m:
            return m.group(1).strip()
        return self.NO