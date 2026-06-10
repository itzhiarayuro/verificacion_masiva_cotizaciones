import streamlit as st
import pandas as pd
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from core.agents.team_orchestrator import AgentTeamOrchestrator

st.title("🤖 9. Equipo de Agentes IA (24 roles)")
st.markdown(
    "Sistema autónomo encabezado por el **Senior Developer**. "
    "Incluye Data Engineering, QA en tiempo real, UI, OCR, Procurement y más."
)

orchestrator = AgentTeamOrchestrator(use_llm=bool(st.session_state.get("api_keys_configured")))
roster = orchestrator.get_roster_summary()
df_roster = pd.DataFrame(roster)

dept_counts = df_roster.groupby("department").size().reset_index(name="Agentes")
st.markdown("### 📋 Organigrama del equipo")
st.dataframe(
    df_roster[["name", "department", "responsibility", "status"]],
    hide_index=True,
    use_container_width=True,
)
st.bar_chart(dept_counts.set_index("department"))

lead = df_roster[df_roster["is_lead"] == True]
if not lead.empty:
    st.success(f"👨‍💻 Líder: **{lead.iloc[0]['name']}** — {lead.iloc[0]['responsibility']}")

if "agent_logs" in st.session_state and st.session_state.agent_logs:
    st.markdown("### 📡 Log en tiempo real (última ejecución)")
    logs_df = pd.DataFrame(st.session_state.agent_logs)
    if not logs_df.empty:
        st.dataframe(logs_df[["agent_name", "status", "message"]].tail(50), hide_index=True, use_container_width=True)

if "qa_results" in st.session_state and st.session_state.qa_results:
    st.markdown("### 🧪 Resultados QA")
    qa = st.session_state.qa_results
    col1, col2, col3 = st.columns(3)
    col1.metric("Tests pasados", f"{qa.get('passed', 0)}/{qa.get('total', 0)}")
    col2.metric("Tasa de éxito", f"{qa.get('pass_rate', 0)}%")
    col3.metric("Estado", qa.get("status", "N/A"))
    if qa.get("tests"):
        st.dataframe(pd.DataFrame(qa["tests"]), hide_index=True, use_container_width=True)

st.info("Los agentes se activan automáticamente en el paso **5. Procesamiento** al iniciar la extracción.")