import streamlit as st
from pathlib import Path

# Page: Revisión de PDFs cargados
st.title("🔎 Revisión de PDFs cargados")

# Si el usuario ya subió PDFs en otras etapas, los guardamos en session_state
if "uploaded_pdfs" not in st.session_state:
    st.session_state.uploaded_pdfs = []

# Permitir cargar más PDFs (en caso de que no se hayan subido aún)
uploaded_file = st.file_uploader("Carga un PDF para revisarlo", type=["pdf"], accept_multiple_files=True)
if uploaded_file:
    for f in uploaded_file:
        # Guardamos el contenido en memoria (bytes) y nombre
        st.session_state.uploaded_pdfs.append({"name": f.name, "bytes": f.read()})
    st.success(f"Se añadieron {len(uploaded_file)} archivo(s) a la lista de revisión.")

if st.session_state.uploaded_pdfs:
    pdf_names = [pdf["name"] for pdf in st.session_state.uploaded_pdfs]
    selected = st.radio("Selecciona el PDF que deseas visualizar", pdf_names)
    # Obtener bytes del PDF seleccionado
    pdf_bytes = next(p["bytes"] for p in st.session_state.uploaded_pdfs if p["name"] == selected)
    # Guardamos temporariamente en disco para que streamlit-pdf-viewer lo lea
    tmp_path = Path("./tmp_pdf_viewer")
    tmp_path.mkdir(exist_ok=True)
    file_path = tmp_path / selected
    with open(file_path, "wb") as out_f:
        out_f.write(pdf_bytes)
    # Mostrar PDF
    try:
        from streamlit_pdf_viewer import pdf_viewer
        pdf_viewer(str(file_path))
    except Exception as e:
        st.error(f"Error al mostrar el PDF: {e}")
else:
    st.info("Aún no has cargado ningún PDF. Usa el cargador de arriba para añadir documentos.")
