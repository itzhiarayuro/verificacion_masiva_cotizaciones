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
    st.info("Para que tu ERP (como SAP o similar) pueda enviarnos cotizaciones, necesitamos prender un servidor interno.")
    
    # Botón para arrancar el servidor usando subprocess
    if "api_running" not in st.session_state:
        st.session_state.api_running = False
        
    if not st.session_state.api_running:
        if st.button("🚀 Encender Servidor API"):
            import subprocess
            import sys
            import os
            # Lanzamos run_api.py en background
            script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "run_api.py"))
            subprocess.Popen([sys.executable, script_path])
            st.session_state.api_running = True
            st.rerun()
    else:
        st.success("✅ El Servidor API está corriendo en http://localhost:8000")
        st.markdown("Tu ERP ya puede hacer peticiones `POST` a `/upload/`.")
        if st.button("🛑 Apagar Servidor"):
            st.session_state.api_running = False
            st.rerun()
            
    st.session_state.data_source = "api"

st.divider()
st.markdown("### 👉 Ve al paso: **3. Tu Excel**")
