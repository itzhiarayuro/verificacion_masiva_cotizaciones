"""Tests for the autonomous multi-agent team (core/agents)."""
import pytest
from core.agents.roles import AGENT_ROSTER, LEAD_AGENT_ID, AgentRole
from core.agents.team_orchestrator import AgentTeamOrchestrator


def test_at_least_20_distinct_roles():
    assert len(AGENT_ROSTER) >= 20
    ids = [r.id for r in AGENT_ROSTER]
    assert len(set(ids)) == len(ids)  # all unique


def test_lead_is_senior_developer():
    assert LEAD_AGENT_ID == "senior_dev"
    lead = next((r for r in AGENT_ROSTER if r.id == LEAD_AGENT_ID), None)
    assert lead is not None
    assert "Senior" in lead.name or "senior" in lead.name.lower()


def test_required_departments_present():
    depts = {r.department for r in AGENT_ROSTER}
    assert "Calidad" in depts or "QA" in depts or any("Calidad" in d or "QA" in d for d in depts)
    assert any("Datos" in d or "Data" in d for d in depts)
    assert any("Liderazgo" in d for d in depts)


def test_all_roles_have_minimal_fields():
    for role in AGENT_ROSTER:
        assert isinstance(role, AgentRole)
        assert role.id and role.name and role.department and role.responsibility


def test_orchestrator_inits_and_reports_roster():
    orch = AgentTeamOrchestrator(use_llm=False)
    roster = orch.get_roster_summary()
    assert len(roster) >= 20
    lead = next((r for r in roster if r["is_lead"]), None)
    assert lead is not None
    assert lead["id"] == "senior_dev"
    assert all("status" in r for r in roster)


def test_process_batch_smoke_without_llm(tmp_path):
    """Smoke test the batch flow (will use table extractor + fallbacks, no LLM)."""
    orch = AgentTeamOrchestrator(use_llm=False)

    # Use the existing sample PDF in the project if available
    sample_pdf = "temp_pdf_viewer/KAIZEN.pdf"
    import os
    if not os.path.exists(sample_pdf):
        # Fallback: create a tiny dummy (won't extract much, but tests the plumbing)
        dummy = tmp_path / "dummy_cot.pdf"
        dummy.write_bytes(b"%PDF-1.4\n% minimal")
        pdf_list = [{"name": "dummy_cot.pdf", "bytes": dummy.read_bytes()}]
    else:
        with open(sample_pdf, "rb") as f:
            pdf_list = [{"name": "KAIZEN.pdf", "bytes": f.read()}]

    result = orch.process_batch(pdf_list)
    assert "rows" in result
    assert "total_rows" in result
    assert "global_qa" in result
    assert "agent_logs" in result
    assert result["total_files"] == 1
    # Even if 0 rows (bad sample pdf), the QA and logging machinery must have run
    assert "status" in result["global_qa"]
