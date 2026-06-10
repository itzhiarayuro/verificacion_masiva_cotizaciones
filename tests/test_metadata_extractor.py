"""Tests for MetadataExtractor (regex + filename based contact/conditions extraction)."""
from core.extraction.metadata_extractor import MetadataExtractor


def test_extract_from_filename():
    meta = MetadataExtractor()
    res = meta.extract("", "Item_415_Cotizacion_2_COVAL.pdf")
    assert res["Proveedor"] in ("COVAL", "NO ESPECIFICADO") or "COVAL" in res["Proveedor"]


def test_nit_extraction():
    meta = MetadataExtractor()
    text = "NIT: 900.372.268-7\nComercial: Ing. Maria Lopez\nventas@acme.co\nTel: 311 555 1212"
    res = meta.extract(text)
    assert "900.372.268-7" in res["NIT"]
    assert "@" in res["Correo"]
    assert "311" in res["Teléfono"] or res["Teléfono"] != "NO ESPECIFICADO"


def test_conditions_extraction():
    meta = MetadataExtractor()
    text = """
    Tiempo de entrega: 15 días calendario
    Forma de pago: 30% anticipo, saldo contra entrega
    Vigencia de la oferta: 45 días
    """
    res = meta.extract(text)
    assert "15" in res["Tiempo Entrega"] or res["Tiempo Entrega"] != "NO ESPECIFICADO"
    assert "anticipo" in res["Forma Pago"].lower() or res["Forma Pago"] != "NO ESPECIFICADO"
    assert "45" in res["Vigencia"] or res["Vigencia"] != "NO ESPECIFICADO"


def test_moneda_detection():
    meta = MetadataExtractor()
    assert meta.extract("Precio en USD 1200")["Moneda"] == "USD"
    assert meta.extract("Total EUR 3400")["Moneda"] == "EUR"
    assert meta.extract("Todo en pesos COP")["Moneda"] == "COP"


def test_fallback_no_especificado():
    meta = MetadataExtractor()
    res = meta.extract("Texto sin nada relevante", "random.pdf")
    assert res["NIT"] == "NO ESPECIFICADO"
    assert res["Correo"] == "NO ESPECIFICADO"
