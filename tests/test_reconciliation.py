"""Tests for ReconciliationEngine (core/reconciliation_engine.py).

Covers the main audit rules used in the export/analysis report:
- Insufficient quotes (< 2)
- Same provider with different prices
- Inconsistent descriptions for the same item
"""
import pytest
from core.reconciliation_engine import ReconciliationEngine


@pytest.fixture
def engine():
    eng = ReconciliationEngine()
    eng.clear_hallazgos()
    return eng


def make_cot(prov, precio, desc="Material X"):
    return {"data": {"Proveedor": prov, "Valor_Sin_IVA": precio, "Descripcion": desc}}


def test_insufficient_cotizaciones(engine):
    res = engine.audit_item("ITM-001", [make_cot("ACME", 100)])
    assert res["estado"] == "CON_DISCREPANCIAS"
    assert any(h["tipo"] == "COTIZACIONES_INSUFICIENTES" for h in engine.hallazgos)


def test_multiple_providers_same_price_ok(engine):
    cots = [
        make_cot("ACME SAS", 1200),
        make_cot("OTRO PROVEEDOR", 1190),
    ]
    res = engine.audit_item("ITM-010", cots)
    # No duplicate provider price conflict
    price_hallazgos = [h for h in engine.hallazgos if h["tipo"] == "PROVEEDOR_MULTIPLE_PRECIOS"]
    assert len(price_hallazgos) == 0
    assert res["estado"] == "APROBADO" or res["estado"] == "CON_DISCREPANCIAS"  # may still have other rules


def test_same_provider_different_prices(engine):
    cots = [
        make_cot("ACME SAS", 1000),
        make_cot("ACME S.A.S.", 1100),  # normalized same provider
    ]
    res = engine.audit_item("ITM-020", cots)
    assert any(h["tipo"] == "PROVEEDOR_MULTIPLE_PRECIOS" for h in engine.hallazgos)
    assert res["estado"] == "CON_DISCREPANCIAS"


def test_inconsistent_descriptions(engine):
    cots = [
        make_cot("P1", 500, "Tubo 1/2 pulgada"),
        make_cot("P2", 520, "Tubo de 3/4"),
    ]
    res = engine.audit_item("ITM-030", cots)
    assert any(h["tipo"] == "DESCRIPCIONES_INCONSISTENTES" for h in engine.hallazgos)
    assert res["estado"] == "CON_DISCREPANCIAS"


def test_best_price_computation(engine):
    cots = [
        make_cot("A", "1.500,00"),
        make_cot("B", 1200),
        make_cot("C", "$1,250.50"),
    ]
    res = engine.audit_item("ITM-040", cots)
    # Should pick the lowest after cleaning
    assert res["mejor_precio"] is not None
    assert res["mejor_precio"] <= 1200


def test_clear_hallazgos_works(engine):
    engine.audit_item("X", [make_cot("P", 10)])
    assert len(engine.hallazgos) > 0
    engine.clear_hallazgos()
    assert len(engine.hallazgos) == 0
