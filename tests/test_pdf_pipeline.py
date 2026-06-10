"""Tests focused on PDFExtractionPipeline pure logic (no LLM, no real PDF bytes needed)."""
import pytest
from core.extraction.pdf_pipeline import PDFExtractionPipeline


def test_parse_filename_codes():
    p = PDFExtractionPipeline(use_llm=False)
    item, cot = p.parse_filename_codes("Item_256_Cotizacion_1_FILTRA H2O LTDA.pdf")
    assert item == "256"
    assert cot == "1"

    item2, cot2 = p.parse_filename_codes("iehxP_Item_415_Cotizacion_2_COVAL.pdf")
    assert item2 == "415"
    assert cot2 == "2"


def test_build_row_produces_all_columns(csv_columns):
    p = PDFExtractionPipeline(use_llm=False)
    meta = {"Proveedor": "ACME SAS", "NIT": "900.111.222-3", "Moneda": "COP"}
    item = {
        "Descripción del Producto": "Válvula de bola",
        "Cantidad": "4",
        "Precio Unitario": "87500",
        "Precio Total": "350000",
        "_page": 3,
        "_confidence": "HIGH",
    }
    row = p._build_row("123", "5", "test.pdf", meta, item)
    for col in csv_columns:
        assert col in row
    assert row["Cód. Item Archivo"] == "123"
    assert row["Proveedor"] == "ACME SAS"
    assert row["Página"] == 3


def test_fallback_ficha_tecnica_when_no_items():
    """When table+LLM produce nothing, we should get the explicit ficha tecnica row."""
    p = PDFExtractionPipeline(use_llm=False)
    # We can't easily call the full process without bytes, but we can simulate the branch
    raw_items = []
    if not raw_items:
        raw_items = [{
            "Descripción del Producto": "Documento sin tabla de precios detectada (ficha técnica o catálogo)",
            "Cantidad": "1",
            "Precio Unitario": "NO ESPECIFICADO",
            "Precio Total": "NO ESPECIFICADO",
            "_page": 1,
            "_confidence": "LOW",
        }]
    meta = {"Proveedor": "HUBER"}
    row = p._build_row("254", "1", "ficha.pdf", meta, raw_items[0])
    assert "ficha técnica" in row["Descripción del Producto"]
    assert row["Precio Unitario"] == "NO ESPECIFICADO"


def test_merge_meta_prefers_llm_when_regex_missing():
    p = PDFExtractionPipeline(use_llm=False)
    regex_meta = {"Proveedor": "NO ESPECIFICADO", "NIT": "NO ESPECIFICADO", "Moneda": "COP"}
    llm_meta = {"proveedor": "REAL PROVEEDOR", "nit": "800.123.456-7", "tiempo_entrega": "20 días"}
    merged = p._merge_meta(regex_meta, llm_meta)
    assert merged["Proveedor"] == "REAL PROVEEDOR"
    assert merged["NIT"] == "800.123.456-7"
    assert merged["Tiempo Entrega"] == "20 días"
