import streamlit as st
import pandas as pd
import io
import os
import sys
from pathlib import Path

# Añadir el path raíz para importar módulos locales
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from core.reconciliation_engine import ReconciliationEngine
from core.extraction.pdf_pipeline import CSV_COLUMNS

st.title("💾 9. Exportación Final")
st.markdown("Todos tus datos han sido procesados y confirmados. Descarga en Excel o CSV consolidado (formato Grok).")

if "extraction_results" not in st.session_state or st.session_state.extraction_results.empty:
    st.warning("⚠️ No hay datos para exportar. Por favor completa los pasos anteriores.")
else:
    df_results = st.session_state.extraction_results
    
    # ----------------------------------------------------
    # Generar Excel 1: Excel CORREGIDO (Resultado limpio)
    # ----------------------------------------------------
    output_corregido = io.BytesIO()
    with pd.ExcelWriter(output_corregido, engine='openpyxl') as writer:
        df_results.to_excel(writer, index=False, sheet_name="Cotizaciones_Extraidas")
    excel_corregido_data = output_corregido.getvalue()
    
    # ----------------------------------------------------
    # Generar Excel 2: Excel de ANÁLISIS (3 hojas)
    # ----------------------------------------------------
    # Ejecutar el Reconciliation Engine usando el esquema real del pipeline
    engine = ReconciliationEngine()
    engine.clear_hallazgos()

    # Usar las columnas oficiales del pipeline cuando estén disponibles
    official_cols = [c for c in CSV_COLUMNS if c in df_results.columns]
    if official_cols:
        df_results = df_results[official_cols].copy()

    # Determinar la columna de ítem real (Cód. Item Archivo es la estándar)
    item_col = None
    for candidate in ["Cód. Item Archivo", "Cód. Cotización Archivo", "Ítem", "item", "Item"]:
        if candidate in df_results.columns:
            item_col = candidate
            break
    if not item_col:
        item_col = df_results.columns[0]

    # Agrupar por ítem usando el esquema Grok real
    cotizaciones_por_item = {}
    for _, row in df_results.iterrows():
        itm_val = str(row.get(item_col, "SIN_ITEM")).strip()
        if itm_val not in cotizaciones_por_item:
            cotizaciones_por_item[itm_val] = []

        prov_val = row.get("Proveedor", "") or ""
        if not prov_val or prov_val == "NO ESPECIFICADO":
            for col in df_results.columns:
                if "proveedor" in col.lower():
                    prov_val = row.get(col, "") or ""
                    break

        # Preferimos Precio Unitario; caemos a Precio Total si no hay
        val_val = row.get("Precio Unitario") or row.get("Precio Total") or 0
        desc_val = row.get("Descripción del Producto", "") or row.get("Descripcion", "")

        cot_dict = {
            "data": {
                "Proveedor": prov_val,
                "Valor_Sin_IVA": val_val,
                "Descripcion": desc_val,
            }
        }
        cotizaciones_por_item[itm_val].append(cot_dict)

    # Auditamos cada ítem (reconciliación de precios / descripciones / cantidad mínima)
    audit_results = []
    for itm_id, cots in cotizaciones_por_item.items():
        res = engine.audit_item(itm_id, cots)
        audit_results.append(res)

    # Crear Hoja 1: Hallazgos de Auditoría
    if engine.hallazgos:
        df_hallazgos = pd.DataFrame(engine.hallazgos)
        df_hallazgos.rename(columns={
            "item": "Ítem",
            "severidad": "Severidad",
            "tipo": "Tipo de Hallazgo",
            "mensaje": "Descripción del Problema"
        }, inplace=True)
    else:
        df_hallazgos = pd.DataFrame([{"Mensaje": "No se encontraron discrepancias. Todo aprobado."}])

    # Crear Hoja 2: Resumen de Métricas
    total_docs = len(df_results)
    total_items = len(cotizaciones_por_item)
    items_con_disc = sum(1 for r in audit_results if r.get("estado") == "CON_DISCREPANCIAS")
    tasa_aprobacion = ((total_items - items_con_disc) / total_items * 100) if total_items > 0 else 100
    ahorro_tiempo_min = total_docs * 15  # 15 minutos por documento

    df_metrics = pd.DataFrame({
        "Métrica": [
            "Total Documentos Procesados",
            "Total Ítems Auditados",
            "Ítems Aprobados sin Novedad",
            "Ítems con Discrepancias",
            "Tasa de Aprobación (%)",
            "Tiempo Ahorrado Estimado (Minutos)"
        ],
        "Valor": [
            total_docs,
            total_items,
            total_items - items_con_disc,
            items_con_disc,
            f"{tasa_aprobacion:.1f}%",
            ahorro_tiempo_min
        ]
    })

    # Crear Hoja 3: Comparativo de Precios (basado en datos reales extraídos)
    comparativo_rows = []
    for itm_id, cots in cotizaciones_por_item.items():
        for c in cots:
            comparativo_rows.append({
                "Ítem": itm_id,
                "Proveedor": c["data"]["Proveedor"],
                "Descripción en Cotización": c["data"]["Descripcion"],
                "Precio Extraído": c["data"]["Valor_Sin_IVA"]
            })
    df_comparativo = pd.DataFrame(comparativo_rows)
    
    # Escribir el Excel de análisis con las 3 hojas en memoria
    output_analisis = io.BytesIO()
    with pd.ExcelWriter(output_analisis, engine='openpyxl') as writer:
        df_hallazgos.to_excel(writer, index=False, sheet_name="Anomalías y Hallazgos")
        df_metrics.to_excel(writer, index=False, sheet_name="Resumen de Métricas")
        df_comparativo.to_excel(writer, index=False, sheet_name="Comparativo de Precios")
    excel_analisis_data = output_analisis.getvalue()
    
    # Usar preferentemente las columnas oficiales del pipeline (Grok format)
    grok_cols = [c for c in CSV_COLUMNS if c not in ("Archivo", "Página", "Confianza", "Estado", "Fuente")]
    export_df = df_results[[c for c in grok_cols if c in df_results.columns]].copy()
    csv_grok = export_df.to_csv(index=False, encoding="utf-8-sig")
    csv_grok_pipe = export_df.to_csv(index=False, sep="|", encoding="utf-8-sig")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### 📊 Excel Consolidado")
        st.download_button(
            "⬇️ Descargar Excel CORREGIDO",
            data=excel_corregido_data,
            file_name="cotizaciones_corregidas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with col2:
        st.markdown("### 📋 CSV Grok (coma)")
        st.info("Formato: 1 fila por ítem, metadatos repetidos — como cotizaciones_consolidadas.csv")
        st.download_button(
            "⬇️ Descargar CSV consolidado",
            data=csv_grok,
            file_name="cotizaciones_consolidadas.csv",
            mime="text/csv",
        )

    with col3:
        st.markdown("### 📋 CSV Grok (pipe |)")
        st.download_button(
            "⬇️ Descargar CSV pipe",
            data=csv_grok_pipe,
            file_name="cotizaciones_consolidadas_pipe.csv",
            mime="text/csv",
        )

    st.markdown("### 📈 Reporte de Análisis y Auditoría")
    st.download_button(
        "⬇️ Descargar Excel de ANÁLISIS",
        data=excel_analisis_data,
        file_name="reporte_analisis_auditoria.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
        
    st.divider()
    st.balloons()
    st.success(f"🎉 ¡Has terminado! Te has ahorrado aproximadamente **{ahorro_tiempo_min / 60:.1f} horas** de trabajo manual con este lote.")
    
if st.button("🧹 Limpiar Sesión y Empezar de Nuevo"):
    st.session_state.clear()
    st.rerun()
