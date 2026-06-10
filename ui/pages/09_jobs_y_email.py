"""
Página de configuración y monitoreo: Jobs + Email (nuevo sistema escalable).

Esta es la interfaz principal para 1M PDFs + ingesta continua de correos.
"""
import streamlit as st
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.db import init_db, list_jobs, get_job
from core.job_manager import get_job_manager
from core.email_ingest import ingest_gmail_to_job
from core.email_reader import EmailReader

st.set_page_config(page_title="Jobs & Email - Auditor", layout="wide")
st.title("⚙️ 9. Jobs Masivos + Email (Sistema Escalable)")

st.caption("Usa el nuevo JobManager + workers + object storage. Ideal para > 1.000 PDFs y/o ingesta automática de Gmail.")

init_db()
mgr = get_job_manager()

# ---------------- Sidebar config ----------------
with st.sidebar:
    st.header("Configuración del Lote")
    llm_mode = st.selectbox("LLM Mode (ahorro masivo)", ["none", "fallback", "always"], index=0,
                            help="'none' = solo tablas (recomendado para 1M+). 'fallback' = LLM solo si fallan tablas.")
    batch_size = st.slider("Tamaño de batch por worker", 10, 200, 50)
    notify = st.text_input("Email de notificación (al terminar)", value="")

    st.divider()
    st.markdown("**Worker**")
    st.code("python -m workers.simple_worker", language="bash")
    st.caption("Corre en otra terminal. Procesa jobs pendientes en lotes pequeños.")

# ---------------- Crear Job desde Upload ----------------
st.subheader("📤 Crear Job desde archivos locales")
uploaded = st.file_uploader("Sube PDFs (se registran en storage + DB)", type=["pdf"], accept_multiple_files=True)

col1, col2 = st.columns(2)
with col1:
    if st.button("🚀 Crear Job + Encolar (recomendado para >500)", disabled=not uploaded):
        pdf_list = [{"name": f.name, "bytes": f.read()} for f in uploaded]
        job = mgr.create_upload_job(
            pdf_list,
            llm_mode=llm_mode,
            batch_size=batch_size,
            notify_email=notify or None,
        )
        # kick first batch immediately (background in real worker is better)
        mgr.process_job_small_batch(job.id, max_files=batch_size)
        st.success(f"Job creado: {job.id}")
        st.session_state["last_job_id"] = job.id
        st.rerun()

with col2:
    if st.button("🔄 Refrescar lista de jobs"):
        st.rerun()

# ---------------- Email Ingest (REAL ahora) ----------------
st.subheader("📧 Ingesta desde Gmail (real, paginado)")
st.markdown("Usa tu `credentials.json` + `token.json`. La consulta soporta miles de mensajes.")

email_query = st.text_input("Query Gmail", value="has:attachment filename:pdf newer_than:2025/01/01")
max_msgs = st.number_input("Máx. mensajes a revisar", 10, 2000, 100)

if st.button("📥 Crear Job desde Gmail + empezar procesamiento"):
    try:
        job = ingest_gmail_to_job(
            query=email_query,
            max_messages=int(max_msgs),
            llm_mode=llm_mode,
            notify_email=notify or None,
        )
        st.success(f"Job de email creado: {job.id} con {job.total_files} PDFs encontrados.")
        st.session_state["last_job_id"] = job.id
        st.rerun()
    except Exception as e:
        st.error(f"Error en ingesta Gmail: {e}")
        st.info("Asegúrate de tener credentials.json en la raíz y haber completado el flujo OAuth una vez.")

# ---------------- Jobs recientes + progreso ----------------
st.subheader("📋 Jobs recientes (DB)")

jobs = list_jobs(limit=30)
if not jobs:
    st.info("Aún no hay jobs. Crea uno arriba o ejecuta el worker.")
else:
    for j in jobs:
        with st.expander(f"{j.id[:8]} | {j.status} | {j.processed_files}/{j.total_files} files | {j.total_rows} rows | llm={j.llm_mode}"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Progreso", f"{j.progress_pct}%")
            c2.metric("Filas", j.total_rows)
            c3.metric("Fuente", j.source_type)

            st.caption(f"Creado: {j.created_at} | Storage: {j.storage_prefix}")

            if st.button(f"Avanzar batch ahora (hasta {j.batch_size})", key=f"adv_{j.id}"):
                res = mgr.process_job_small_batch(j.id, max_files=j.batch_size or 50)
                st.write(res)
                st.rerun()

            if j.agent_logs:
                st.markdown("**Últimos eventos de agentes (24 roles):**")
                for log in j.agent_logs[-8:]:
                    st.text(f"[{log.get('ts','')[:19]}] {log.get('agent_id')}: {log.get('message')}")

# ---------------- Ayuda rápida ----------------
st.divider()
st.markdown("""
**Cómo usarlo a escala:**
1. (Opcional) `docker compose up -d` → levanta Redis + MinIO.
2. En una terminal: `python init_db.py`
3. En otra: `python -m workers.simple_worker`
4. Usa esta página o la API `/api/v1/jobs` y `/api/v1/jobs/ingest-email` para crear trabajo.
5. Los workers procesan en tandas pequeñas, escriben Parquet a `storage/`, actualizan la DB.
6. Para 1M+ cambia a Celery + múltiples workers + MinIO.

El modo antiguo (páginas 2-8) sigue funcionando para lotes pequeños interactivos.
""")
