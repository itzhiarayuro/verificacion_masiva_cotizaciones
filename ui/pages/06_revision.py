import streamlit as st
import pandas as pd

st.title("✅ 6. Revisión Final (Human-in-the-loop)")
st.markdown("Revisa los datos antes de exportarlos a tu Excel final. Si algo está mal, cámbialo directamente aquí.")

# Mock data de resultados
df_results = pd.DataFrame({
    "Archivo": ["Cotizacion_A.pdf", "Cot_B.pdf", "Factura_C.pdf", "Presupuesto_D.pdf"],
    "Valor Sin IVA": [15000, 30000, None, 60000],
    "Proveedor": ["Empresa A", "Empresa B", None, "Empresa D"],
    "Confianza": ["🟢 ALTA (Gemini)", "🟢 ALTA (Gemini)", "🔴 REVISIÓN MANUAL", "🟡 MEDIA (NVIDIA)"]
})

st.markdown("### Tabla Editable de Resultados")
edited_df = st.data_editor(
    df_results,
    disabled=["Archivo", "Confianza"],
    hide_index=True,
    use_container_width=True
)

st.divider()

st.markdown("### ⚠️ Corrección Manual de Errores")
st.error("El archivo `Factura_C.pdf` falló todas las extracciones de IA. Por favor indícale a la IA dónde mirar o digita el valor tú mismo.")

col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("**Visor del Documento Original:**")
    st.info("(Aquí se renderiza el PDF visualmente usando streamlit-pdf-viewer)")
    # pdf_viewer("path/to/pdf")

with col2:
    st.markdown("**Solución Manual:**")
    valor_manual = st.number_input("Ingresa el valor numérico aquí:", value=0)
    proveedor_manual = st.text_input("Ingresa el proveedor aquí:")
    
    st.markdown("**O dale una pista a la IA y reintenta:**")
    pista = st.text_area("Ej: Busca en la esquina inferior derecha debajo de 'Total Neto'")
    st.button("🔄 Reintentar Extracción con esta pista")

st.divider()
st.markdown("### 👉 Ve al último paso: **7. Exportar**")
