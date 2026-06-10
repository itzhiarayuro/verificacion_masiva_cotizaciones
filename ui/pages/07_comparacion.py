import streamlit as st
import pandas as pd
import re
import tempfile
import zipfile
import os
import shutil
from pathlib import Path
from st_aggrid import GridOptionsBuilder, AgGrid

# Reutilizamos el pipeline y el equipo de agentes real (lógica Grok)
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from core.extraction.pdf_pipeline import PDFExtractionPipeline, CSV_COLUMNS
from core.agents.team_orchestrator import AgentTeamOrchestrator

st.set_page_config(page_title="Comparación Excel ↔ PDFs", layout="wide")

st.title("🔍 7. Comparación Excel ↔ PDFs (Verificación Masiva)")
st.caption("Usa el mismo motor de extracción de 24 agentes (Senior Dev + QA realtime + Data Engineering) que el flujo principal.")

# ----------------------------------------------------------------------
# 1️⃣  CARGAR EXCEL (hoja de referencia / pedido) -----------------------
# ----------------------------------------------------------------------
excel_file = st.file_uploader(
    "📥 Subir hoja de cotización / pedido Excel (puede tener encabezados dobles)",
    type=["xlsx"],
    key="compare_excel",
)

def flatten_multiindex(columns: pd.MultiIndex) -> list[str]:
    flat = []
    for lvl0, lvl1 in columns:
        if pd.isna(lvl0) or lvl0 == "":
            flat.append(str(lvl1).strip())
        elif pd.isna(lvl1) or lvl1 == "":
            flat.append(str(lvl0).strip())
        else:
            flat.append(f"{str(lvl0).strip()} – {str(lvl1).strip()}")
    return flat

if excel_file is not None:
    df_raw = pd.read_excel(excel_file, header=[0, 1])
    if isinstance(df_raw.columns, pd.MultiIndex):
        df_raw.columns = flatten_multiindex(df_raw.columns)

    # Alias útiles para matching posterior
    for col in df_raw.columns:
        low = str(col).lower()
        if "ítem" in low or low == "item":
            df_raw["_item_key"] = df_raw[col].astype(str).str.strip()
        if "descripción" in low or "descripcion" in low:
            df_raw["_desc_key"] = df_raw[col].astype(str).str.strip().str.upper()

    st.session_state["excel_ref"] = df_raw
    st.success("✅ Hoja Excel de referencia cargada")
    st.dataframe(df_raw.head(8), use_container_width=True)
else:
    st.info("Sube tu Excel de referencia para poder cruzar contra las cotizaciones en PDF.")

# ----------------------------------------------------------------------
# 2️⃣  SUBIR PDFs o ZIP (estructura libre o por carpetas) --------------
# ----------------------------------------------------------------------
if "compare_pdfs" not in st.session_state:
    st.session_state["compare_pdfs"] = []

pdf_uploads = st.file_uploader(
    "📂 PDFs individuales o ZIP (con subcarpetas Item_XXX / Cot_YYY o planas)",
    type=["pdf", "zip"],
    accept_multiple_files=True,
    key="compare_pdfs_uploader",
)

if pdf_uploads:
    temp_dir = tempfile.mkdtemp(prefix="compare_pdfs_")
    extracted = []

    for up in pdf_uploads:
        if up.name.lower().endswith(".zip"):
            zpath = os.path.join(temp_dir, up.name)
            with open(zpath, "wb") as zf:
                zf.write(up.read())
            with zipfile.ZipFile(zpath, "r") as zf:
                zf.extractall(temp_dir)
        else:
            # PDF suelto
            ppath = os.path.join(temp_dir, up.name)
            with open(ppath, "wb") as pf:
                pf.write(up.read())

    # Recolectar todos los PDFs encontrados (recursivo)
    for root, _, files in os.walk(temp_dir):
        for fname in files:
            if fname.lower().endswith(".pdf"):
                full = os.path.join(root, fname)
                extracted.append({"name": fname, "path": full})

    # Convertir a formato que usa el orquestador (bytes en memoria)
    prepared = []
    for e in extracted:
        try:
            with open(e["path"], "rb") as f:
                prepared.append({"name": e["name"], "bytes": f.read()})
        except Exception:
            pass

    st.session_state["compare_pdfs"] = prepared
    st.success(f"✅ {len(prepared)} PDF(s) listos para extracción con el equipo de agentes.")

if st.session_state.get("compare_pdfs"):
    st.write(f"**{len(st.session_state['compare_pdfs'])}** archivo(s) en cola para comparación.")

# ----------------------------------------------------------------------
# 3️⃣  EXTRAER CON EL EQUIPO REAL (24 agentes + QA realtime) -----------
# ----------------------------------------------------------------------
col_a, col_b = st.columns(2)
with col_a:
    use_main_results = st.checkbox("Usar resultados ya procesados en el Paso 5 (si existen)", value=True)

with col_b:
    run_btn = st.button("🚀 Extraer PDFs con Equipo de Agentes (Grok style)")

if run_btn and st.session_state.get("compare_pdfs"):
    api_ready = bool(st.session_state.get("api_keys_configured")) and bool(os.getenv("GEMINI_API_KEY"))
    orch = AgentTeamOrchestrator(use_llm=api_ready)

    progress = st.progress(0)
    status = st.empty()

    def on_evt(evt):
        if evt.get("type") == "file_start":
            status.text(f"Procesando {evt.get('file')} ...")
        elif evt.get("type") == "file_done":
            progress.progress(evt.get("index", 1) / max(evt.get("total", 1), 1))

    batch = orch.process_batch(st.session_state["compare_pdfs"], on_event=on_evt)
    st.session_state["compare_extracted"] = pd.DataFrame(batch["rows"]) if batch.get("rows") else pd.DataFrame(columns=CSV_COLUMNS)
    st.session_state["compare_qa"] = batch.get("global_qa", {})
    progress.progress(1.0)
    status.text(f"✅ Extracción completada: {len(st.session_state['compare_extracted'])} filas. QA: {batch.get('global_qa', {}).get('status')}")
    st.rerun()

# También podemos heredar del flujo principal
if use_main_results and "extraction_results" in st.session_state and not st.session_state.extraction_results.empty:
    if "compare_extracted" not in st.session_state or st.session_state.get("compare_extracted") is None or len(st.session_state.get("compare_extracted", [])) == 0:
        st.session_state["compare_extracted"] = st.session_state["extraction_results"].copy()
        st.info("Usando los resultados del flujo principal (Paso 5).")

# Mostrar preview de lo extraído para comparación
if "compare_extracted" in st.session_state and not st.session_state["compare_extracted"].empty:
    st.markdown("### 📊 Datos extraídos de los PDFs (usando pipeline real)")
    st.dataframe(st.session_state["compare_extracted"].head(12), use_container_width=True)
    if "compare_qa" in st.session_state:
        qa = st.session_state["compare_qa"]
        st.caption(f"QA Global: {qa.get('status')} — {qa.get('passed', 0)}/{qa.get('total', 0)} tests ({qa.get('pass_rate', 0)}%)")

# ----------------------------------------------------------------------
# 4️⃣  COMPARAR --------------------------------------------------------
# ----------------------------------------------------------------------
if st.button("🔎 Ejecutar Comparación Excel ↔ PDFs Extraídos") and "excel_ref" in st.session_state and "compare_extracted" in st.session_state:
    excel_df = st.session_state["excel_ref"].copy()
    pdf_df = st.session_state["compare_extracted"].copy()

    # Construir llaves de cruce
    if "_item_key" not in excel_df.columns:
        for c in excel_df.columns:
            if "ítem" in str(c).lower() or str(c).lower() == "item":
                excel_df["_item_key"] = excel_df[c].astype(str).str.strip()
                break
    if "_item_key" not in excel_df.columns:
        excel_df["_item_key"] = excel_df.iloc[:, 0].astype(str).str.strip()

    if "_desc_key" not in excel_df.columns:
        for c in excel_df.columns:
            lc = str(c).lower()
            if "descripción" in lc or "descripcion" in lc:
                excel_df["_desc_key"] = excel_df[c].astype(str).str.upper().str.strip()
                break
    if "_desc_key" not in excel_df.columns:
        excel_df["_desc_key"] = ""

    # Para los PDFs extraídos usamos el esquema oficial
    pdf_df["_item_key"] = pdf_df.get("Cód. Item Archivo", pdf_df.get("Cód. Cotización Archivo", "")).astype(str).str.strip()
    pdf_df["_desc_key"] = pdf_df.get("Descripción del Producto", "").astype(str).str.upper().str.strip()

    # Clave compuesta robusta
    excel_df["join_key"] = (excel_df["_item_key"].str.upper() + "||" + excel_df["_desc_key"].str[:60]).str.strip()
    pdf_df["join_key"] = (pdf_df["_item_key"].str.upper() + "||" + pdf_df["_desc_key"].str[:60]).str.strip()

    merged = pd.merge(
        excel_df, pdf_df,
        on="join_key",
        how="outer",
        suffixes=("_excel", "_pdf"),
        indicator=True
    )

    coincidencias = merged[merged["_merge"] == "both"].copy()
    solo_excel = merged[merged["_merge"] == "left_only"].copy()
    solo_pdf = merged[merged["_merge"] == "right_only"].copy()

    st.subheader("✅ Coincidencias (Excel ↔ PDF)")

    # Intentar detectar columnas de precio en el Excel para marcar diferencias
    price_candidates = [c for c in excel_df.columns if any(k in str(c).lower() for k in ["valor", "precio", "unit", "total", "iva"])]
    if price_candidates and "Precio Unitario" in coincidencias.columns:
        for pc in price_candidates[:2]:
            def _diff(row, col_excel=pc):
                try:
                    e = float(str(row.get(col_excel, 0)).replace(".", "").replace(",", ".").strip() or 0)
                    p = float(str(row.get("Precio Unitario", 0)).replace(".", "").replace(",", ".").strip() or 0)
                    return abs(e - p) / max(abs(e), 1) > 0.05 if e and p else False
                except Exception:
                    return False
            coincidencias[f"diff_{pc[:20]}"] = coincidencias.apply(_diff, axis=1)

    gb = GridOptionsBuilder.from_dataframe(coincidencias.head(200))
    gb.configure_default_column(filterable=True, sortable=True, resizable=True)
    AgGrid(coincidencias, gridOptions=gb.build(), height=320, use_container_width=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("⚠️ Solo en Excel (faltan en PDFs)")
        AgGrid(solo_excel[[c for c in solo_excel.columns if not c.endswith("_pdf")]].head(100), height=220, use_container_width=True)
    with c2:
        st.subheader("⚠️ Solo en PDFs (no estaban en Excel)")
        AgGrid(solo_pdf[[c for c in solo_pdf.columns if not c.endswith("_excel")]].head(100), height=220, use_container_width=True)
    with c3:
        st.metric("Filas coincidentes", len(coincidencias))
        st.metric("Solo Excel", len(solo_excel))
        st.metric("Solo PDFs", len(solo_pdf))

    if st.button("💾 Descargar reporte de verificación (XLSX)"):
        out_path = Path("outputs") / f"verificacion_masiva_{pd.Timestamp.now():%Y%m%d_%H%M%S}.xlsx"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            coincidencias.to_excel(writer, sheet_name="Coincidencias", index=False)
            solo_excel.to_excel(writer, sheet_name="Solo_Excel", index=False)
            solo_pdf.to_excel(writer, sheet_name="Solo_PDFs", index=False)
            if "compare_qa" in st.session_state:
                pd.DataFrame([st.session_state["compare_qa"]]).to_excel(writer, sheet_name="QA_Summary", index=False)
        with open(out_path, "rb") as f:
            st.download_button("⬇️ Descargar XLSX de verificación", data=f.read(), file_name=out_path.name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    if not st.session_state.get("excel_ref") or not st.session_state.get("compare_extracted"):
        st.info("Carga el Excel de referencia + extrae los PDFs (o usa los del Paso 5) para habilitar la comparación.")