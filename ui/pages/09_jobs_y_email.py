"""
Página 10: Jobs Masivos + Email + Export + Monitoreo (sistema escalable completo).

Incluye:
- Creación de jobs (upload / Gmail ingest real)
- Lista de jobs con progreso
- Progreso "en vivo" por job (polling + botón Monitor)
- Lista de archivos en storage por job (shards + consolidados)
- Botones: Exportar consolidado (parquet/xlsx), Enviar email ahora, Forzar avance
- Overview de cola (pending/processing counts)
- Instrucciones para workers simples y Celery + múltiples workers
- Integración con EmailSender y export
"""
import streamlit as st
import os
import sys
import time
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.db import init_db, list_jobs, get_job, update_job
from core.job_manager import get_job_manager, export_consolidated_for_job
from core.email_ingest import ingest_gmail_to_job
from core.storage import get_storage
from core.db import finalize_and_notify
from core.export import list_job_files

st.set_page_config(page_title="Jobs + Email + Export - Auditor Escala", layout="wide")
st.title("🚀 10. Jobs Masivos + Email + Export Consolidado")

st.caption("Sistema listo para 1M+ PDFs. Workers procesan en tandas pequeñas. Resultados en Parquet/Excel consolidados.")

init_db()
mgr = get_job_manager()
storage = get_storage()

# ==================== SIDEBAR / CONFIG GLOBAL ====================
with st.sidebar:
    st.header("⚙️ Configuración de nuevo Job")
    llm_mode = st.selectbox("LLM Mode (ahorro crítico)", ["none", "fallback", "always"], index=0,
                            help="none = solo tablas (recomendado masivo). fallback = LLM solo si fallan tablas.")
    batch_size = st.slider("Batch size por iteración de worker", 10, 300, 50)
    notify_email = st.text_input("Notificar por email al terminar", placeholder="tu@empresa.com")
    max_split = st.number_input("Auto-split si > N archivos (jobs grandes)", 100, 10000, 2000)

    st.divider()
    st.markdown("### 🛠️ Workers")
    st.code("python -m workers.simple_worker", language="bash")
    st.caption("Corra esto en 1 o varias terminales. Es el modo fácil (sin Redis).")

    if st.button("🔄 Refrescar todo"):
        st.rerun()

# ==================== QUEUE OVERVIEW ====================
st.subheader("📊 Estado de la Cola (Jobs)")

jobs_all = list_jobs(limit=100)
pending = [j for j in jobs_all if j.status == "pending"]
processing = [j for j in jobs_all if j.status == "processing"]
done = [j for j in jobs_all if j.status in ("completed", "partial")]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Pendientes", len(pending))
c2.metric("Procesando", len(processing))
c3.metric("Terminados", len(done))
c4.metric("Total jobs", len(jobs_all))

if pending or processing:
    st.info(f"Hay trabajo pendiente. Asegúrate de tener workers corriendo (simple_worker o Celery).")

st.caption("**Manejo de errores en export masivo**: recolecta fallos por-shard, low-memory por defecto, manifest.json con detalles, y los errores **no son fatales** para el job.")

# ==================== CREAR JOBS ====================
st.subheader("📤 Crear Job")

tab1, tab2 = st.tabs(["Subir PDFs locales", "Ingesta Gmail (real)"])

with tab1:
    uploaded = st.file_uploader("Arrastra PDFs para crear Job escalable", type=["pdf"], accept_multiple_files=True, key="job_upload")
    use_celery = st.checkbox("Encolar vía Celery (requiere Redis)", value=False, key="cel_local")
    if st.button("Crear Job + empezar procesamiento", disabled=not uploaded, type="primary"):
        pdf_list = [{"name": f.name, "bytes": f.read()} for f in uploaded]
        job = mgr.create_upload_job(
            pdf_list, llm_mode=llm_mode, batch_size=batch_size, notify_email=notify_email or None,
            max_files_per_subjob=int(max_split)
        )
        from core.job_manager import enqueue_job_batch
        enq = enqueue_job_batch(job.id, max_files=batch_size, force_celery=use_celery)
        st.success(f"✅ Job creado: {job.id} (modo: {enq.get('mode')})")
        st.session_state.last_job = job.id
        st.rerun()

with tab2:
    st.markdown("Usa tu cuenta de Gmail real (credentials.json + OAuth). La consulta es paginada.")
    g_query = st.text_input("Query Gmail", value="has:attachment filename:pdf newer_than:2025/01/01", key="gq")
    g_max = st.number_input("Máximo mensajes a escanear", 5, 2000, 150)
    use_celery_g = st.checkbox("Encolar vía Celery (Redis)", value=False, key="cel_gmail")
    if st.button("📧 Crear Job desde Gmail + procesar", type="primary"):
        try:
            job = ingest_gmail_to_job(
                query=g_query, max_messages=int(g_max), llm_mode=llm_mode, notify_email=notify_email or None,
                # max_files_per_subjob passed via the updated helper
            )
            from core.job_manager import enqueue_job_batch
            enq = enqueue_job_batch(job.id, max_files=30, force_celery=use_celery_g)
            st.success(f"✅ Job de email creado: {job.id} (modo: {enq.get('mode')}) — {job.total_files} PDFs")
            st.session_state.last_job = job.id
            st.rerun()
        except Exception as e:
            st.error(f"Error Gmail: {e}")
            st.caption("Necesitas credentials.json en la raíz y completar OAuth una vez.")

# ==================== JOBS LIST + ACCIONES ====================
st.subheader("📋 Jobs (clic para detalles y acciones)")

if not jobs_all:
    st.warning("No hay jobs todavía. Crea uno arriba.")
else:
    for j in jobs_all[:25]:  # limit display
        status_emoji = {"pending": "⏳", "processing": "🔄", "completed": "✅", "partial": "⚠️", "failed": "❌"}.get(j.status, "•")
        title = f"{status_emoji} {j.id[:8]} | {j.status} | {j.processed_files}/{j.total_files} PDFs | {j.total_rows} filas | llm={j.llm_mode}"

        with st.expander(title, expanded=(st.session_state.get("last_job") == j.id)):
            colA, colB, colC = st.columns([2, 2, 2])

            with colA:
                st.progress(min(j.progress_pct or 0, 100) / 100)
                st.caption(f"Progreso: {j.progress_pct}% | Creado: {j.created_at}")

                if st.button("Avanzar 1 batch ahora", key=f"adv_{j.id}"):
                    res = mgr.process_job_small_batch(j.id, max_files=j.batch_size or 50)
                    st.write(res)
                    st.rerun()

                if st.button("Finalizar + Notificar + Exportar", key=f"fin_{j.id}"):
                    finalize_and_notify(j.id, also_export=True)
                    st.success("finalize_and_notify ejecutado")
                    st.rerun()

            with colB:
                st.markdown("**Acciones de export y email (mejorado manejo de errores)**")
                if st.button("📦 Exportar consolidado (low-memory + Parquet)", key=f"exp_{j.id}"):
                    with st.spinner("Export masivo en curso (low memory mode)..."):
                        res = export_consolidated_for_job(j.id, formats=["parquet", "xlsx"], low_memory=True)
                    st.json(res)
                    if not res.get("success"):
                        st.warning("Export parcial o con errores - revisa la lista de errores abajo.")
                    st.rerun()

                # Incremental / filtered export controls
                colf1, colf2 = st.columns(2)
                with colf1:
                    prov_f = st.text_input("Filtrar por Proveedor (contiene)", key=f"prov_{j.id}", placeholder="PAVCO o METAL")
                with colf2:
                    fecha_f = st.text_input("Filtrar por fecha (Vigencia/Archivo)", key=f"fecha_{j.id}", placeholder="2025/06")
                grp = st.selectbox("Agrupar export por...", [None, "Proveedor"], key=f"grp_{j.id}")
                if st.button("Export FILTRADO / AGRUPADO", key=f"fexp_{j.id}"):
                    with st.spinner("Export incremental/filtrado..."):
                        res = export_consolidated_for_job(
                            j.id, formats=["parquet"], low_memory=True,
                            filter_proveedor=prov_f or None,
                            filter_fecha_desde=fecha_f or None,
                            group_by=grp,
                        )
                    st.json(res)
                    st.rerun()

                if j.notify_email and st.button("✉️ Enviar resumen por email ahora", key=f"mail_{j.id}"):
                    try:
                        from core.email_sender import EmailSender
                        sender = EmailSender()
                        sender.send_job_summary(j)
                        st.success(f"Email enviado a {j.notify_email}")
                    except Exception as e:
                        st.error(f"Fallo al enviar: {e}")

                if getattr(j, "export_manifest_key", None):
                    st.info(f"Manifest detallado: {j.export_manifest_key}")
                if j.result_manifest_key:
                    st.success(f"Consolidado principal: {j.result_manifest_key}")

                # Show export errors if any
                export_errs = getattr(j, "export_errors", None) or []
                if export_errs:
                    st.error(f"⚠️ {len(export_errs)} errores en último export (shards fallidos o problemas de escritura)")
                    with st.expander("Ver errores de export"):
                        for err in export_errs[:10]:
                            st.code(str(err))

            with colC:
                st.markdown("**Archivos en Storage**")
                files = list_job_files(j.id)
                if files:
                    for f in files[:15]:
                        icon = "📊" if f["is_result"] else "📄"
                        st.text(f"{icon} {f['key']} ({f.get('size',0)} bytes)")
                else:
                    st.caption("Aún no hay archivos (o storage local vacío)")

            # Agent logs
            if j.agent_logs:
                st.markdown("**Últimos logs de los 24 agentes**")
                for log in j.agent_logs[-12:]:
                    st.code(f"[{log.get('ts','')[:19]}] {log.get('agent_id','?')}: {log.get('message','')}", language=None)

            # Live monitor button
            if st.button("👁️ Monitorear en vivo (polling 5s)", key=f"mon_{j.id}"):
                placeholder = st.empty()
                for i in range(12):  # ~1 minute of monitoring
                    fresh = get_job(j.id)
                    if fresh:
                        with placeholder.container():
                            st.progress(min(fresh.progress_pct or 0, 100)/100)
                            st.write(f"Estado: {fresh.status} | Procesados: {fresh.processed_files}/{fresh.total_files} | Filas: {fresh.total_rows}")
                            if fresh.agent_logs:
                                st.dataframe(fresh.agent_logs[-6:], use_container_width=True, hide_index=True)
                    if fresh and fresh.status in ("completed", "partial", "failed"):
                        st.success("¡Job terminado!")
                        break
                    time.sleep(5)
                    st.rerun()  # force refresh of the whole page state

# ==================== INSTRUCCIONES WORKERS / CELERY ====================
st.divider()
st.subheader("🧵 Cómo correr Workers (fácil vs producción)")

colw1, colw2 = st.columns(2)
with colw1:
    st.markdown("**Modo fácil (recomendado para empezar, Windows friendly)**")
    st.code("""
# Terminal 1 (o varias)
python -m workers.simple_worker

# Una sola pasada
python -m workers.simple_worker --once --batch 100
""", language="bash")
    st.caption("Usa DB polling. Corre varias instancias en paralelo sin problema.")

with colw2:
    st.markdown("**Modo Celery + Redis (múltiples workers reales, recomendado >50k PDFs)**")
    st.code("""
# 1. Levantar Redis (docker o nativo)
docker compose up -d redis

# 2. Worker(s) - puedes abrir 4 terminales o usar -c
celery -A workers.celery_app worker -Q default -c 4 --loglevel=info

# O múltiples workers dedicados
celery -A workers.celery_app worker --concurrency=2 -n worker1@%h
celery -A workers.celery_app worker --concurrency=2 -n worker2@%h

# Opcional: beat para tareas periódicas (ingesta email programada)
celery -A workers.celery_app beat --loglevel=info
""", language="bash")

st.info("En la creación de jobs (arriba o vía API) se puede elegir encolar en Celery cuando esté disponible. El simple_worker siempre funciona como fallback.")

st.caption("Los workers llaman automáticamente a finalize_and_notify (email + export consolidado) cuando un job termina.")

# Quick test note
if st.checkbox("Mostrar comando rápido de prueba (crea job dummy + avanza)"):
    st.code("python -c \"from core.db import init_db; from core.job_manager import get_job_manager; init_db(); jm=get_job_manager(); j=jm.create_upload_job([{'name':'demo.pdf','bytes':b'%PDF'}], llm_mode='none'); print(j.id); jm.process_job_small_batch(j.id)\"")
