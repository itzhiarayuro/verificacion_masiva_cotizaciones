import streamlit as st
import pandas as pd
import time
import os
import sys

# Añadir el path raíz para importar módulos locales si se requiere en el futuro
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from ui.components.live_excel_preview import render_live_preview

st.title("⏳ 5. Procesamiento y Live Preview")

data_source = st.session_state.get("data_source", "local")

if data_source == "local":
    uploaded_pdfs = st.file_uploader("Arrastra aquí todos tus PDFs (sin límite):", type=["pdf"], accept_multiple_files=True)
elif data_source == "gmail":
    st.info("Utilizando 15 PDFs descargados automáticamente desde tu Gmail.")
    uploaded_pdfs = [1] * 15 # Mock

if st.button("🚀 Iniciar Extracción con IA"):
    st.markdown("### Procesando documentos...")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Mock data para la animación tipo "Live Preview"
    df = pd.DataFrame({
        "Archivo": ["Cotizacion_A.pdf", "Cot_B.pdf", "Factura_C.pdf", "Presupuesto_D.pdf"],
        "Valor Sin IVA": ["", "", "", ""],
        "Proveedor": ["", "", "", ""],
        "Estado": ["Pendiente", "Pendiente", "Pendiente", "Pendiente"]
    })
    
    grid_placeholder = st.empty()
    
    # Animación simulada del procesamiento en vivo
    for i in range(4):
        # Actualizar grid
        with grid_placeholder.container():
            render_live_preview(df, key=f"grid_{i}")
            
        status_text.text(f"Analizando {df.iloc[i]['Archivo']}...")
        time.sleep(1) # Simula tiempo de llamada a LLM
        
        # Llenar datos
        df.at[i, "Valor Sin IVA"] = f"${(i+1)*15000}"
        df.at[i, "Proveedor"] = f"Empresa {chr(65+i)}"
        df.at[i, "Estado"] = "✅ Completado" if i != 2 else "⚠️ Revisión Manual"
        
        progress_bar.progress((i + 1) / 4)
        
    with grid_placeholder.container():
        render_live_preview(df, key="grid_final")
        
    st.success("¡Procesamiento finalizado! El 95% de los datos se extrajo con alta confianza.")
    st.markdown("### 👉 Ve al paso: **6. Revisión Final**")
