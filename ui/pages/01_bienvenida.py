import streamlit as st
import os

st.title("👋 Bienvenido al Auditor de Cotizaciones V3")
st.markdown("""
Esta herramienta te ahorrará cientos de horas extrayendo datos de PDFs e imágenes automáticamente hacia tu archivo Excel.
No necesitas saber de programación. Solo sigue los pasos en la barra lateral.
""")

st.header("1️⃣ Configuración Inicial")
st.info("Para que la Inteligencia Artificial funcione, necesitamos conectarla. No te preocupes, usaremos los servicios GRATUITOS.")

st.markdown("Obtén tu llave gratuita aquí: [Google AI Studio](https://aistudio.google.com/app/apikey)")
gemini_key = st.text_input("Llave Gratuita de Google Gemini:", type="password", value=os.getenv("GEMINI_API_KEY", ""))

st.markdown("Obtén tu llave gratuita aquí: [NVIDIA Build](https://build.nvidia.com/)")
nvidia_key = st.text_input("Llave Gratuita de NVIDIA (Opcional):", type="password", value=os.getenv("NVIDIA_API_KEY", ""))

if st.button("Guardar y Continuar"):
    if gemini_key:
        os.environ["GEMINI_API_KEY"] = gemini_key
        st.session_state.api_keys_configured = True
        st.success("✅ ¡Configurado! Ya puedes usar la IA gratis.")
    else:
        st.warning("⚠️ Sería ideal poner la llave, pero puedes continuar para probar la plataforma con datos simulados.")
        st.session_state.api_keys_configured = True

st.divider()
if st.session_state.get("api_keys_configured"):
    st.markdown("### 👉 Ve al siguiente paso en la barra lateral: **2. Origen de Datos**")
