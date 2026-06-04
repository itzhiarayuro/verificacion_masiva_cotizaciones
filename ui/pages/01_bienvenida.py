import streamlit as st
import os

st.title("👋 Bienvenido al Auditor de Cotizaciones V3")
st.markdown("""
Esta herramienta te ahorrará cientos de horas extrayendo datos de PDFs e imágenes automáticamente hacia tu archivo Excel.
No necesitas saber de programación. Solo sigue los pasos en la barra lateral.
""")

st.header("1️⃣ Configuración Inicial")
st.info("Para que la Inteligencia Artificial funcione, necesitamos tus llaves de acceso (API Keys). Solo se guardan localmente en tu computadora.")

gemini_key = st.text_input("Google Gemini API Key (Extractor Principal):", type="password", value=os.getenv("GEMINI_API_KEY", ""))
nvidia_key = st.text_input("NVIDIA NIM API Key (Revisor / 2da opinión):", type="password", value=os.getenv("NVIDIA_API_KEY", ""))

if st.button("Guardar y Probar Conexión"):
    if gemini_key:
        # En producción esto escribiría en el .env
        os.environ["GEMINI_API_KEY"] = gemini_key
        st.session_state.api_keys_configured = True
        st.success("✅ ¡Llaves configuradas! Gemini está listo.")
    else:
        st.error("⚠️ La llave de Gemini es obligatoria.")

st.divider()
if st.session_state.get("api_keys_configured"):
    st.markdown("### 👉 Ve al siguiente paso en la barra lateral: **2. Origen de Datos**")
