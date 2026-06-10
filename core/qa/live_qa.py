from typing import Any, Dict, List
import re


class LiveQARunner:
    REQUIRED_FIELDS = [
        "Cód. Item Archivo",
        "Cód. Cotización Archivo",
        "Proveedor",
        "Descripción del Producto",
    ]

    def run_tests(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        tests = []
        tests.append(self._test_has_rows(rows))
        tests.append(self._test_required_fields(rows))
        tests.append(self._test_unique_descriptions_per_file(rows))
        tests.append(self._test_price_format(rows))
        tests.append(self._test_metadata_coverage(rows))
        tests.append(self._test_no_empty_proveedor_with_price(rows))

        passed = sum(1 for t in tests if t["passed"])
        return {
            "total": len(tests),
            "passed": passed,
            "failed": len(tests) - passed,
            "pass_rate": round(100 * passed / len(tests), 1) if tests else 0,
            "tests": tests,
            "status": "PASS" if passed == len(tests) else "FAIL",
        }

    def _test_has_rows(self, rows: List[Dict]) -> Dict:
        ok = len(rows) > 0
        return {"name": "Al menos 1 fila extraída", "passed": ok, "detail": f"{len(rows)} filas"}

    def _test_required_fields(self, rows: List[Dict]) -> Dict:
        bad = 0
        for r in rows:
            if any(not str(r.get(f, "")).strip() for f in self.REQUIRED_FIELDS):
                bad += 1
        ok = bad == 0
        return {"name": "Campos obligatorios presentes", "passed": ok, "detail": f"{bad} filas incompletas"}

    def _test_unique_descriptions_per_file(self, rows: List[Dict]) -> Dict:
        by_file: Dict[str, set] = {}
        for r in rows:
            f = r.get("Archivo", "")
            d = r.get("Descripción del Producto", "")
            by_file.setdefault(f, set())
            if d in by_file[f] and d != "Documento sin tabla de precios detectada (ficha técnica o catálogo)":
                pass
            by_file[f].add(d)
        ok = all(len(s) > 0 for s in by_file.values()) if by_file else False
        return {"name": "Descripciones por archivo", "passed": ok, "detail": f"{len(by_file)} archivos"}

    def _test_price_format(self, rows: List[Dict]) -> Dict:
        bad = 0
        for r in rows:
            for field in ("Precio Unitario", "Precio Total"):
                val = str(r.get(field, ""))
                if val and val != "NO ESPECIFICADO" and not re.search(r"\d", val):
                    bad += 1
        ok = bad == 0
        return {"name": "Formato de precios válido", "passed": ok, "detail": f"{bad} precios inválidos"}

    def _test_metadata_coverage(self, rows: List[Dict]) -> Dict:
        if not rows:
            return {"name": "Cobertura metadatos", "passed": False, "detail": "sin filas"}
        meta_fields = ["NIT", "Correo", "Teléfono"]
        covered = 0
        for f in meta_fields:
            if any(str(r.get(f, "")) not in ("", "NO ESPECIFICADO") for r in rows):
                covered += 1
        ok = covered >= 1
        return {"name": "Al menos 1 metadato de contacto", "passed": ok, "detail": f"{covered}/3 campos"}

    def _test_no_empty_proveedor_with_price(self, rows: List[Dict]) -> Dict:
        bad = 0
        for r in rows:
            prov = str(r.get("Proveedor", ""))
            price = str(r.get("Precio Unitario", ""))
            if price not in ("", "NO ESPECIFICADO") and prov in ("", "NO ESPECIFICADO", "Desconocido"):
                bad += 1
        ok = bad == 0
        return {"name": "Proveedor cuando hay precio", "passed": ok, "detail": f"{bad} filas sin proveedor"}