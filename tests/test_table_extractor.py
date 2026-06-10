"""Unit tests for TableExtractor (pdfplumber table + text fallback parsing)."""
import pytest
from core.extraction.table_extractor import TableExtractor


@pytest.fixture
def extractor():
    return TableExtractor()


def test_parse_simple_table(extractor):
    table = [
        ["Descripción", "Cant", "P.Unit", "Total"],
        ["Tubo PRFV DN400", "10", "125000", "1250000"],
        ["Codo 90° 4\"", "5", "87500", "437500"],
    ]
    rows = extractor._parse_table(table)
    assert len(rows) == 2
    assert rows[0]["Descripción del Producto"] == "Tubo PRFV DN400"
    assert rows[0]["Cantidad"] == "10"
    assert rows[0]["Precio Unitario"] == "125000"
    assert rows[1]["Precio Total"] == "437500"


def test_skips_header_row_in_data(extractor):
    table = [
        ["Descripción", "Cantidad", "P.Unit", "Total"],
        ["Descripción", "Cantidad", "Precio", "Total"],  # header-like row that should be ignored
        ["Tubería 6m", "20", "45000", "900000"],
    ]
    rows = extractor._parse_table(table)
    assert len(rows) >= 1
    assert any("Tubería" in r.get("Descripción del Producto", "") for r in rows)


def test_text_line_parsing(extractor):
    text = """
    Algo de texto previo
    Ducto PRFV 0.42m  7.55  150000  1132500
    Codo galvanizado 3"   12   34500   414000
    """
    rows = extractor._parse_text_lines(text)
    assert len(rows) >= 2
    assert "Ducto" in rows[0]["Descripción del Producto"]
    assert rows[0]["Cantidad"] == "7.55"


def test_dedupe(extractor):
    items = [
        {"Descripción del Producto": "Tubo", "Precio Unitario": "100"},
        {"Descripción del Producto": "Tubo", "Precio Unitario": "100"},  # duplicate
        {"Descripción del Producto": "Codo", "Precio Unitario": "50"},
    ]
    deduped = extractor._dedupe(items)
    assert len(deduped) == 2


def test_no_pdfplumber_graceful(extractor, monkeypatch):
    # Force unavailable
    import core.extraction.table_extractor as te_mod
    monkeypatch.setattr(te_mod, "PDFPLUMBER_AVAILABLE", False)
    rows = extractor.extract_from_pdf("nonexistent.pdf")
    assert rows == []
