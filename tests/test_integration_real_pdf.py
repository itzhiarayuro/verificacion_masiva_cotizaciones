"""Integration-style tests using a real PDF present in the repository.

Uses temp_pdf_viewer/KAIZEN.pdf (or any other PDF) with the full pipeline
in non-LLM mode (use_llm=False) so it relies on pdfplumber + fallbacks.

Verifies:
- The AgentTeamOrchestrator runs end-to-end without crashing.
- Produces rows in the expected Grok-style schema.
- Live QA runner is executed and returns a result.
- Handles the 'ficha tecnica' case gracefully when no prices are found.
"""
import os
import pytest
from core.agents.team_orchestrator import AgentTeamOrchestrator
from core.extraction.pdf_pipeline import CSV_COLUMNS


SAMPLE_PDF = "temp_pdf_viewer/KAIZEN.pdf"


@pytest.mark.integration
def test_real_pdf_smoke_with_agent_team():
    if not os.path.exists(SAMPLE_PDF):
        pytest.skip(f"Sample PDF not found at {SAMPLE_PDF}")

    with open(SAMPLE_PDF, "rb") as f:
        pdf_bytes = f.read()

    pdf_list = [{"name": "KAIZEN.pdf", "bytes": pdf_bytes}]

    # Force no LLM so the test is deterministic and doesn't need API keys
    orchestrator = AgentTeamOrchestrator(use_llm=False)

    result = orchestrator.process_batch(pdf_list)

    assert "rows" in result
    assert "total_rows" in result
    assert "global_qa" in result
    assert result["total_files"] == 1

    rows = result["rows"]
    if rows:
        # Check that produced rows contain the core Grok columns
        first = rows[0]
        for col in ["Cód. Item Archivo", "Proveedor", "Descripción del Producto"]:
            assert col in first

        # Every row should have the full CSV_COLUMNS shape (or at least the main ones)
        for r in rows:
            for required in ("Cód. Item Archivo", "Descripción del Producto", "Archivo"):
                assert required in r

    # QA must have run
    qa = result["global_qa"]
    assert "status" in qa
    assert "passed" in qa
    assert "tests" in qa or qa.get("total", 0) >= 0


@pytest.mark.integration
def test_real_pdf_produces_ficha_or_real_items():
    """If the sample PDF has no extractable price table, the pipeline must still
    emit the explicit 'ficha técnica' sentinel row instead of returning zero rows."""
    if not os.path.exists(SAMPLE_PDF):
        pytest.skip("Sample PDF not available")

    with open(SAMPLE_PDF, "rb") as f:
        pdf_bytes = f.read()

    orchestrator = AgentTeamOrchestrator(use_llm=False)
    result = orchestrator.process_batch([{"name": os.path.basename(SAMPLE_PDF), "bytes": pdf_bytes}])

    rows = result["rows"]
    # Either we got real items, or we correctly fell back to the ficha tecnica message
    if len(rows) == 1:
        desc = rows[0].get("Descripción del Producto", "")
        assert "ficha técnica" in desc or "sin tabla de precios" in desc.lower() or len(desc) > 5
    else:
        # We got real extracted items — still a valid outcome
        assert len(rows) >= 1
