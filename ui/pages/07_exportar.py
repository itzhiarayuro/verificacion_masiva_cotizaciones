import streamlit as st

st.title("💾 7. Exportación Exitosa")
st.markdown("Todos tus datos han sido procesados y confirmados. Ya puedes descargar tus archivos.")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 📊 Tu Excel Consolidado")
    st.info("Este es el archivo final con todas las filas agregadas en las columnas correctas.")
    st.download_button("⬇️ Descargar Excel.xlsx", data=b"mock_excel_data", file_name="cotizaciones_auditadas.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with col2:
    st.markdown("### 📈 Reporte de Análisis")
    st.info("Métricas de ahorro de tiempo, tokens usados y desempeño de Gemini vs NVIDIA.")
    st.download_button("⬇️ Descargar Reporte.pdf", data=b"mock_report_data", file_name="reporte_auditoria.pdf", mime="application/pdf")

st.divider()
st.balloons()
st.success("🎉 ¡Has terminado! Te has ahorrado aproximadamente **4 horas** de trabajo manual con este lote.")
if st.button("🧹 Limpiar Sesión y Empezar de Nuevo"):
    st.session_state.clear()
    st.rerun()
