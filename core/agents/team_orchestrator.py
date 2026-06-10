import time
from typing import Any, Callable, Dict, List, Optional

from core.extraction.pdf_pipeline import PDFExtractionPipeline, CSV_COLUMNS
from core.qa.live_qa import LiveQARunner
from .roles import AGENT_ROSTER, LEAD_AGENT_ID


class AgentTeamOrchestrator:
    """
    Equipo autónomo de 24 agentes (simulado para UI + logs).
    El Senior Developer encabeza el flujo.
    Cada agente reporta estado en tiempo real vía callback.

    Now also supports llm_mode for the new job system.
    Old process_batch path remains for small interactive runs in Streamlit.
    """

    def __init__(self, use_llm: bool = True, llm_mode: str | None = None):
        self.roster = AGENT_ROSTER
        self.pipeline = PDFExtractionPipeline(use_llm=use_llm, llm_mode=llm_mode)
        self.qa = LiveQARunner()
        self.agent_logs: List[Dict[str, Any]] = []
        self.agent_status: Dict[str, str] = {a.id: "idle" for a in self.roster}

    def get_roster_summary(self) -> List[Dict[str, str]]:
        return [
            {
                "id": a.id,
                "name": a.name,
                "department": a.department,
                "responsibility": a.responsibility,
                "status": self.agent_status.get(a.id, "idle"),
                "is_lead": a.id == LEAD_AGENT_ID,
            }
            for a in self.roster
        ]

    def _set_status(self, agent_id: str, status: str, message: str = ""):
        self.agent_status[agent_id] = status
        self.agent_logs.append({
            "agent_id": agent_id,
            "agent_name": next((a.name for a in self.roster if a.id == agent_id), agent_id),
            "status": status,
            "message": message,
            "timestamp": time.time(),
        })

    def process_batch(
        self,
        pdf_list: List[Dict[str, Any]],
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
        llm_mode: str | None = None,
    ) -> Dict[str, Any]:
        """Legacy small-batch path (still used by Streamlit live preview for < few hundred PDFs).
        For 1M+ use JobManager + workers instead.
        """
        def emit(event: Dict):
            if on_event:
                on_event(event)

        if llm_mode:
            # Re-create pipeline with desired mode for this run
            self.pipeline = PDFExtractionPipeline(use_llm=bool(llm_mode != "none"), llm_mode=llm_mode)

        self._set_status(LEAD_AGENT_ID, "active", f"Coordinando extracción de {len(pdf_list)} PDFs")
        emit({"type": "lead_start", "total": len(pdf_list), "agents": len(self.roster)})

        for agent in self.roster:
            if agent.id != LEAD_AGENT_ID:
                self._set_status(agent.id, "standby", "Esperando asignación")

        all_rows: List[Dict[str, Any]] = []
        per_file_qa: List[Dict] = []

        for idx, pdf_info in enumerate(pdf_list):
            filename = pdf_info["name"]
            pdf_bytes = pdf_info["bytes"]

            self._set_status("devops", "active", f"Preparando {filename}")
            self._set_status("pdf_analyst", "active", f"Analizando {filename}")
            emit({"type": "file_start", "file": filename, "index": idx + 1, "total": len(pdf_list)})

            def on_progress(agent_id: str, msg: str):
                self._set_status(agent_id, "active", msg)
                emit({"type": "agent_log", "agent_id": agent_id, "message": msg, "file": filename})

            rows = self.pipeline.process_pdf_bytes(filename, pdf_bytes, on_progress=on_progress)
            all_rows.extend(rows)

            self._set_status("qa_live", "active", f"QA en tiempo real: {filename}")
            qa_result = self.qa.run_tests(rows)
            per_file_qa.append({"file": filename, **qa_result})
            emit({"type": "qa_result", "file": filename, "qa": qa_result})

            self._set_status("csv_exporter", "active", f"{len(rows)} filas listas de {filename}")
            emit({"type": "file_done", "file": filename, "rows": len(rows), "index": idx + 1, "total": len(pdf_list)})

        self._set_status("reconciliation", "active", "Auditoría final del lote")
        global_qa = self.qa.run_tests(all_rows)

        self._set_status(LEAD_AGENT_ID, "done", f"Completado: {len(all_rows)} filas de {len(pdf_list)} PDFs")
        for agent in self.roster:
            if self.agent_status.get(agent.id) not in ("done", "failed"):
                self._set_status(agent.id, "done", "Lote completado")

        result = {
            "rows": all_rows,
            "columns": CSV_COLUMNS,
            "total_rows": len(all_rows),
            "total_files": len(pdf_list),
            "global_qa": global_qa,
            "per_file_qa": per_file_qa,
            "agent_logs": self.agent_logs[-200:],
            "roster": self.get_roster_summary(),
        }
        emit({"type": "batch_done", "result_summary": {"rows": len(all_rows), "qa": global_qa["status"]}})
        return result