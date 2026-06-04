import streamlit as st
import pandas as pd
import io
import os
import sys
from pathlib import Path

# Añadir el path raíz para importar módulos locales
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from core.reconciliation_engine import ReconciliationEngine

st.title("💾 7. Exportación Final")
st.markdown("Todos tus datos han sido procesados y confirmados. Ya puedes descargar tus reportes en Excel.")

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
    # Ejecutar el Reconciliation Engine
    engine = ReconciliationEngine()
    engine.clear_hallazgos()
    
    # Intentar identificar la columna de "Ítem"
    item_col = None
    for col in df_results.columns:
        if "ítem" in col.lower() or "item" in col.lower():
            item_col = col
            break
            
    # Si no se encuentra columna de Ítem, usamos la primera columna o creamos una dummy
    if not item_col:
        item_col = df_results.columns[3] if len(df_results.columns) > 3 else df_results.columns[0]
        
    # Agrupar las cotizaciones por ítem para el motor de reconciliación
    items_auditados = []
    # Convertir las filas del dataframe en el formato que espera el ReconciliationEngine
    cotizaciones_por_item = {}
    for index, row in df_results.iterrows():
        itm_val = str(row[item_col])
        if itm_val not in cotizaciones_por_item:
            cotizaciones_por_item[itm_val] = []
        
        # Obtener los datos necesarios para el validador
        prov_val = row.get("Proveedor", "")
        if not prov_val:
            # Buscar cualquier columna que contenga "proveedor"
            for col in df_results.columns:
                if "proveedor" in col.lower():
                    prov_val = row.get(col, "")
                    break
        
        val_val = row.get("Valor Sin IVA", row.get("Valor_Unitario", row.get("Valor_Total", 0)))
        desc_val = row.get("Descripción_Material", row.get("Referencia_Eléctrica", ""))
        
        cot_dict = {
            "data": {
                "Proveedor": prov_val,
                "Valor_Sin_IVA": val_val,
                "Descripcion": desc_val
            }
        }
        cotizaciones_por_item[itm_val].append(cot_dict)
        
    # Auditamos cada ítem
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
    items_con_disc = sum(1 for r in audit_results if r["estado"] == "CON_DISCREPANCIAS")
    tasa_aprobacion = ((total_items - items_con_disc) / total_items * 100) if total_items > 0 else 100
    ahorro_tiempo_min = total_docs * 15 # 15 minutos por documento
    
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
    
    # Crear Hoja 3: Comparativo de Precios
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
    
    # Renderizar UI
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📊 Tu Excel Consolidado")
        st.info("Este archivo contiene la tabla limpia de resultados con las correcciones manuales que hiciste.")
        st.download_button(
            "⬇️ Descargar Excel CORREGIDO", 
            data=excel_corregido_data, 
            file_name="cotizaciones_corregidas.xlsx", 
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    with col2:
        st.markdown("### 📈 Reporte de Análisis y Auditoría")
        st.info("Contiene 3 hojas de análisis: Anomalías detectadas, Métricas del lote y Comparativo de precios.")
        st.download_button(
            "⬇️ Descargar Excel de ANÁLISIS", 
            data=excel_analisis_data, 
            file_name="reporte_analisis_auditoria.xlsx", 
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    st.divider()
    st.balloons()
    st.success(f"🎉 ¡Has terminado! Te has ahorrado aproximadamente **{ahorro_tiempo_min / 60:.1f} horas** de trabajo manual con este lote.")
    
if st.button("🧹 Limpiar Sesión y Empezar de Nuevo"):
    st.session_state.clear()
    st.rerun()
