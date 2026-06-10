import streamlit as st
import pandas as pd
import time
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from ui.components.live_excel_preview import render_live_preview
from core.agents.team_orchestrator import AgentTeamOrchestrator
from core.extraction.pdf_pipeline import CSV_COLUMNS

st.title("⏳ 5. Procesamiento y Live Preview")

data_source = st.session_state.get("data_source", "local")

if "uploaded_pdfs" not in st.session_state:
    st.session_state.uploaded_pdfs = []
if "extraction_results" not in st.session_state:
    st.session_state.extraction_results = None
if "agent_logs" not in st.session_state:
    st.session_state.agent_logs = []
if "qa_results" not in st.session_state:
    st.session_state.qa_results = None

uploaded_files = []

if data_source == "local":
    uploaded_files = st.file_uploader(
        "Arrastra aquí todos tus PDFs (sin límite):",
        type=["pdf"],
        accept_multiple_files=True,
    )
elif data_source == "gmail":
    st.info("Utilizando PDFs descargados automáticamente desde tu Gmail.")
    st.session_state.uploaded_pdfs = [
        {"name": "Gmail_Cotizacion_Maquinaria.pdf", "bytes": b"%PDF-1.4 mock content"},
        {"name": "Gmail_Presupuesto_Materiales.pdf", "bytes": b"%PDF-1.4 mock content"},
    ]

if data_source == "local" and uploaded_files:
    current_names = [f.name for f in uploaded_files]
    saved_names = [pdf["name"] for pdf in st.session_state.uploaded_pdfs]
    if current_names != saved_names:
        st.session_state.uploaded_pdfs = []
        st.session_state.extraction_results = None
        for f in uploaded_files:
            file_bytes = f.read()
            f.seek(0)
            st.session_state.uploaded_pdfs.append({"name": f.name, "bytes": file_bytes})

if st.session_state.uploaded_pdfs:
    st.success(f"📂 {len(st.session_state.uploaded_pdfs)} archivo(s) listo(s) para procesar.")
else:
    st.warning("⚠️ Por favor sube al menos un PDF antes de continuar.")

st.markdown("### 🤖 Equipo autónomo (24 agentes)")
st.caption("Encabezado por Senior Developer · Incluye Data Engineering, QA live, OCR, Procurement, UI y más.")

if st.button("🚀 Iniciar Extracción Masiva (estilo Grok)") and st.session_state.uploaded_pdfs:
    api_ready = st.session_state.get("api_keys_configured", False) and os.getenv("GEMINI_API_KEY")

    progress_bar = st.progress(0)
    status_text = st.empty()
    agent_log_box = st.empty()
    grid_placeholder = st.empty()

    orchestrator = AgentTeamOrchestrator(use_llm=api_ready)
    results_list = []
    agent_messages = []
    total_files = len(st.session_state.uploaded_pdfs)

    def on_event(event):
        nonlocal results_list, agent_messages
        if event["type"] == "agent_log":
            agent_messages.append(f"[{event['agent_id']}] {event['message']}")
            agent_log_box.code("\n".join(agent_messages[-15:]), language=None)
        elif event["type"] == "file_start":
            status_text.text(f"📄 Procesando {event['file']} ({event['index']}/{event['total']})...")
        elif event["type"] == "file_done":
            progress_bar.progress(event["index"] / event["total"])
        elif event["type"] == "qa_result":
            qa = event["qa"]
            status_text.text(f"🧪 QA {event['file']}: {qa['passed']}/{qa['total']} tests OK")

    status_text.text("👨‍💻 Senior Developer iniciando pipeline...")
    batch_result = orchestrator.process_batch(st.session_state.uploaded_pdfs, on_event=on_event)

    results_list = batch_result["rows"]
    st.session_state.agent_logs = batch_result["agent_logs"]
    st.session_state.qa_results = batch_result["global_qa"]

    live_df = pd.DataFrame(results_list, columns=CSV_COLUMNS) if results_list else pd.DataFrame(columns=CSV_COLUMNS)
    st.session_state.extraction_results = live_df

    with grid_placeholder.container():
        render_live_preview(live_df, key="grid_final")

    progress_bar.progress(1.0)
    status_text.text(f"✅ Completado: {batch_result['total_rows']} filas de {batch_result['total_files']} PDFs")
    st.rerun()

if st.session_state.extraction_results is not None and not st.session_state.extraction_results.empty:
    st.success(
        f"🎉 Procesamiento finalizado: **{len(st.session_state.extraction_results)}** líneas "
        f"(1 fila por producto/servicio, metadatos repetidos — estilo Grok)."
    )

    if st.session_state.qa_results:
        qa = st.session_state.qa_results
        c1, c2, c3 = st.columns(3)
        c1.metric("QA Tests", f"{qa['passed']}/{qa['total']}")
        c2.metric("Tasa QA", f"{qa['pass_rate']}%")
        c3.metric("Estado QA", qa["status"])

    st.markdown("### 📊 Vista Previa de Datos Extraídos")
    render_live_preview(st.session_state.extraction_results, key="grid_persistente")
    st.markdown("### 👉 Ve a **6. Revisión Final** o **9. Equipo de Agentes** para auditar.")