import streamlit as st

st.title("🔗 4. Asistente de Mapeo de Columnas")

if st.session_state.get("custom_excel"):
    st.markdown("Como subiste tu propio Excel, necesitamos que le digas a la IA dónde poner cada dato extraído.")
    
    st.markdown("### Selecciona a qué columna de tu Excel corresponde cada campo:")
    
    # Mock data for UI demonstration
    columnas_excel = ["Seleccionar...", "Columna_A", "Precio", "Impuesto", "Total", "Nombre_Proveedor"]
    
    col1, col2 = st.columns(2)
    with col1:
        st.selectbox("Dato Extraído: Valor SIN IVA", columnas_excel, index=2)
        st.selectbox("Dato Extraído: Valor del IVA", columnas_excel, index=3)
        st.selectbox("Dato Extraído: Valor CON IVA", columnas_excel, index=4)
    with col2:
        st.selectbox("Dato Extraído: Nombre del Proveedor", columnas_excel, index=5)
        st.selectbox("Dato Extraído: Fecha Cotización", columnas_excel, index=0)
        
    if st.button("💾 Guardar Mapeo"):
        st.success("Mapeo guardado en config.json exitosamente. ¡La IA ya sabe qué hacer!")
else:
    st.success("Estás usando una de nuestras plantillas. El mapeo ya está configurado automáticamente.")

st.divider()
st.markdown("### 👉 Ve al paso: **5. Procesamiento**")
