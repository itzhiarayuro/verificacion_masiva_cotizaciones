import streamlit as st

st.title("📥 2. Origen de los Datos")
st.markdown("¿De dónde quieres que la aplicación saque los PDFs de cotizaciones?")

opcion = st.radio(
    "Selecciona una opción:",
    ["📂 Subir carpeta desde mi computadora", "📧 Extraer adjuntos desde mi Gmail", "🔗 Recibir desde mi ERP (Vía API)"]
)

if opcion.startswith("📂"):
    st.info("Perfecto. En el paso 5 podrás arrastrar tus PDFs.")
    st.session_state.data_source = "local"
elif opcion.startswith("📧"):
    st.warning("Esta opción requiere autenticar tu cuenta de Google.")
    if st.button("Conectar con Gmail"):
        st.success("Simulación: ¡Gmail conectado exitosamente! Hemos encontrado 15 PDFs recientes.")
        st.session_state.data_source = "gmail"
        st.session_state.email_pdfs = ["cotizacion_1.pdf", "cotizacion_2.pdf"] # mock
elif opcion.startswith("🔗"):
    st.info("Inicia el script `run_api.py` en tu terminal para habilitar los Endpoints REST para tu ERP.")
    st.session_state.data_source = "api"

st.divider()
st.markdown("### 👉 Ve al paso: **3. Tu Excel**")
