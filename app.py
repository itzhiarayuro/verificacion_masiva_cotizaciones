import streamlit as st
import os

st.set_page_config(page_title="Auditor de Cotizaciones V3", page_icon="🏢", layout="wide")

# Inicializar estado
if "api_keys_configured" not in st.session_state:
    st.session_state.api_keys_configured = bool(os.getenv("GEMINI_API_KEY"))

if "session_id" not in st.session_state:
    st.session_state.session_id = None

# Definir páginas
p1 = st.Page("ui/pages/01_bienvenida.py", title="1. Configuración", icon="⚙️")
p2 = st.Page("ui/pages/02_origen_datos.py", title="2. Origen de Datos", icon="📥")
p3 = st.Page("ui/pages/03_plantillas_y_excel.py", title="3. Tu Excel", icon="📊")
p4 = st.Page("ui/pages/04_mapeo_columnas.py", title="4. Mapeo de Columnas", icon="🔗")
p5 = st.Page("ui/pages/05_procesamiento_live.py", title="5. Procesamiento", icon="⏳")
p6 = st.Page("ui/pages/06_revision.py", title="6. Revisión Final", icon="✅")
p7 = st.Page("ui/pages/07_exportar.py", title="7. Exportar", icon="💾")

pg = st.navigation([p1, p2, p3, p4, p5, p6, p7])
pg.run()
