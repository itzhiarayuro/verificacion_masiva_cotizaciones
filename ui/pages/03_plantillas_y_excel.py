import streamlit as st
import os

st.title("📊 3. Tu Archivo Excel")
st.markdown("¿En qué formato quieres consolidar la información?")

tab1, tab2 = st.tabs(["⬇️ Usar una Plantilla (Recomendado)", "📁 Subir mi propio Excel"])

with tab1:
    st.markdown("Descarga uno de nuestros formatos probados. Si usas uno de estos, **te saltas el paso 4 de mapeo**.")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.button("🏗️ Obra Civil (PTAR)", help="Ideal para materiales de construcción.")
    with col2:
        st.button("🚜 Alquiler Equipos", help="Ideal para maquinaria pesada.")
    with col3:
        st.button("⚡ Material Eléctrico", help="Ideal para fichas técnicas.")

with tab2:
    st.markdown("Arrastra aquí tu propio archivo de Excel vacío (o con datos previos).")
    uploaded_excel = st.file_uploader("Sube tu archivo .xlsx", type=["xlsx"])
    if uploaded_excel:
        st.success("Excel cargado correctamente.")
        st.session_state.custom_excel = uploaded_excel.name
        st.info("Como es un Excel propio, por favor ve al Paso 4 para decirle a la IA qué es cada columna.")

st.divider()
st.markdown("### 👉 Ve al paso: **4. Mapeo de Columnas** (Si subiste Excel propio) o **5. Procesamiento** (Si usas plantilla)")
