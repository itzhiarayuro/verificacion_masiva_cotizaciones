"""Pytest fixtures for the Auditor de Cotizaciones test suite."""
import pytest
import pandas as pd
from typing import List, Dict, Any

from core.extraction.pdf_pipeline import CSV_COLUMNS
from core.qa.live_qa import LiveQARunner


@pytest.fixture
def sample_good_rows() -> List[Dict[str, Any]]:
    """Typical rows produced by the Grok-style pipeline."""
    return [
        {
            "Cód. Item Archivo": "256",
            "Cód. Cotización Archivo": "1",
            "Proveedor": "FILTRA H2O LTDA",
            "Descripción del Producto": "Ducto en PRFV de diámetro 0,42",
            "Cantidad": "7.55",
            "Precio Unitario": "150000",
            "Precio Total": "1132500",
            "NIT": "900.372.268-7",
            "Moneda": "COP",
            "Tiempo Entrega": "15 días",
            "Forma Pago": "50% anticipo",
            "Vigencia": "30 días",
            "Comercial": "Ing. Juan Perez",
            "Correo": "ventas@filtra.co",
            "Teléfono": "3112345678",
            "Archivo": "Item_256_Cotizacion_1_FILTRA.pdf",
            "Página": 2,
            "Confianza": "HIGH",
            "Estado": "✅ Completado",
            "Fuente": "tabla",
        },
        {
            "Cód. Item Archivo": "172",
            "Cód. Cotización Archivo": "2",
            "Proveedor": "METALURGICA CONSTRUCEL SAS",
            "Descripción del Producto": "BRIDA ROSCADA DN 3 ANSI",
            "Cantidad": "3",
            "Precio Unitario": "189480",
            "Precio Total": "568440",
            "NIT": "900.111.222-3",
            "Moneda": "COP",
            "Tiempo Entrega": "NO ESPECIFICADO",
            "Forma Pago": "NO ESPECIFICADO",
            "Vigencia": "NO ESPECIFICADO",
            "Comercial": "NO ESPECIFICADO",
            "Correo": "NO ESPECIFICADO",
            "Teléfono": "NO ESPECIFICADO",
            "Archivo": "Item_172_Cotizacion_2_METACOL.pdf",
            "Página": 1,
            "Confianza": "MEDIUM",
            "Estado": "✅ Completado",
            "Fuente": "tabla+ia",
        },
    ]


@pytest.fixture
def sample_ficha_tecnica_row() -> List[Dict[str, Any]]:
    return [
        {
            "Cód. Item Archivo": "254",
            "Cód. Cotización Archivo": "1",
            "Proveedor": "HUBER",
            "Descripción del Producto": "Documento sin tabla de precios detectada (ficha técnica o catálogo)",
            "Cantidad": "1",
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
            "Archivo": "Item_254_Cotizacion_1_Reja HUBER.pdf",
            "Página": 1,
            "Confianza": "LOW",
            "Estado": "✅ Completado",
            "Fuente": "tabla",
        }
    ]


@pytest.fixture
def sample_bad_rows() -> List[Dict[str, Any]]:
    """Rows that should trigger several QA failures."""
    return [
        {
            "Cód. Item Archivo": "",
            "Cód. Cotización Archivo": "1",
            "Proveedor": "NO ESPECIFICADO",
            "Descripción del Producto": "",
            "Cantidad": "1",
            "Precio Unitario": "abc",  # bad price
            "Precio Total": "123",
            "NIT": "",
            "Moneda": "COP",
            "Tiempo Entrega": "",
            "Forma Pago": "",
            "Vigencia": "",
            "Comercial": "",
            "Correo": "",
            "Teléfono": "",
            "Archivo": "bad.pdf",
            "Página": 1,
            "Confianza": "LOW",
            "Estado": "✅ Completado",
            "Fuente": "tabla",
        },
        {
            "Cód. Item Archivo": "999",
            "Cód. Cotización Archivo": "9",
            "Proveedor": "",  # empty provider but has price
            "Descripción del Producto": "Tubo",
            "Cantidad": "2",
            "Precio Unitario": "50000",
            "Precio Total": "100000",
            "NIT": "NO ESPECIFICADO",
            "Moneda": "COP",
            "Tiempo Entrega": "NO ESPECIFICADO",
            "Forma Pago": "NO ESPECIFICADO",
            "Vigencia": "NO ESPECIFICADO",
            "Comercial": "NO ESPECIFICADO",
            "Correo": "NO ESPECIFICADO",
            "Teléfono": "NO ESPECIFICADO",
            "Archivo": "bad2.pdf",
            "Página": 1,
            "Confianza": "LOW",
            "Estado": "✅ Completado",
            "Fuente": "tabla",
        },
    ]


@pytest.fixture
def qa_runner() -> LiveQARunner:
    return LiveQARunner()


@pytest.fixture
def csv_columns() -> List[str]:
    return CSV_COLUMNS[:]
