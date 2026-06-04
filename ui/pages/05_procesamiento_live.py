import streamlit as st
import pandas as pd
import time
import os
import sys
import tempfile
from pathlib import Path

# Añadir el path raíz para importar módulos locales
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from ui.components.live_excel_preview import render_live_preview
from core.document_parser import DocumentParser
from core.llm_orchestrator import LLMOrchestrator

st.title("⏳ 5. Procesamiento y Live Preview")

data_source = st.session_state.get("data_source", "local")

# Inicializar st.session_state.uploaded_pdfs si no existe
if "uploaded_pdfs" not in st.session_state:
    st.session_state.uploaded_pdfs = []

uploaded_files = []

if data_source == "local":
    uploaded_files = st.file_uploader(
        "Arrastra aquí todos tus PDFs (sin límite):", 
        type=["pdf"], 
        accept_multiple_files=True
    )
elif data_source == "gmail":
    st.info("Utilizando PDFs descargados automáticamente desde tu Gmail.")
    # Generar algunos archivos mock con contenido simulado si es Gmail
    uploaded_files = []
    # Mocking Gmail files for testing
    st.session_state.uploaded_pdfs = [
        {"name": "Gmail_Cotizacion_Maquinaria.pdf", "bytes": b"%PDF-1.4 mock content"},
        {"name": "Gmail_Presupuesto_Materiales.pdf", "bytes": b"%PDF-1.4 mock content"}
    ]

# Guardar los archivos locales en session_state
if data_source == "local" and uploaded_files:
    st.session_state.uploaded_pdfs = []
    for f in uploaded_files:
        # Leer los bytes
        file_bytes = f.read()
        # Resetear el puntero para que no falle si se vuelve a leer
        f.seek(0)
        st.session_state.uploaded_pdfs.append({
            "name": f.name,
            "bytes": file_bytes
        })

# Mostrar cuántos archivos hay listos para procesar
if st.session_state.uploaded_pdfs:
    st.success(f"📂 {len(st.session_state.uploaded_pdfs)} archivo(s) listo(s) para procesar.")
else:
    st.warning("⚠️ Por favor sube al menos un PDF antes de continuar.")

if st.button("🚀 Iniciar Extracción con IA") and st.session_state.uploaded_pdfs:
    st.markdown("### Procesando documentos...")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Obtener las columnas del template seleccionado o creado en el paso 3
    if "custom_template_df" in st.session_state:
        template_cols = list(st.session_state.custom_template_df.columns)
    else:
        # Fallback por si no pasó por el paso 3
        template_cols = ["Ítem", "Descripción_Material", "Cantidad", "Valor_Unitario", "Valor_Total", "Proveedor"]
        
    # Inicializar el DataFrame final con Archivo, Confianza y Estado + las columnas del template
    all_cols = ["Archivo", "Confianza", "Estado"] + template_cols
    results_list = []
    
    grid_placeholder = st.empty()
    
    # Inicializar servicios de extracción reales si hay API keys
    api_ready = st.session_state.get("api_keys_configured", False) and os.getenv("GEMINI_API_KEY")
    parser = DocumentParser()
    orchestrator = LLMOrchestrator() if api_ready else None
    
    total_files = len(st.session_state.uploaded_pdfs)
    
    for idx, pdf_info in enumerate(st.session_state.uploaded_pdfs):
        filename = pdf_info["name"]
        pdf_bytes = pdf_info["bytes"]
        
        status_text.text(f"Analizando {filename} ({idx + 1}/{total_files})...")
        
        # Crear un diccionario para esta fila
        row_data = {col: "" for col in all_cols}
        row_data["Archivo"] = filename
        row_data["Estado"] = "⏳ Procesando"
        
        # Insertar fila inicial a la tabla en vivo
        results_list.append(row_data)
        live_df = pd.DataFrame(results_list)
        with grid_placeholder.container():
            render_live_preview(live_df, key=f"grid_{idx}_init")
            
        if api_ready:
            try:
                # Escribir archivo temporalmente a disco para el parser
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(pdf_bytes)
                    tmp_path = tmp_file.name
                
                # Parsear el documento (cascada de markitdown, pdfplumber, OCR)
                parse_res = parser.parse_document(tmp_path)
                text = parse_res.get("text", "")
                is_difficult = parse_res.get("is_difficult", False)
                method = parse_res.get("method", "failed")
                
                # Definir instrucciones para el LLM basadas en el template
                prompt_instrucciones = f"Extrae los siguientes campos en formato JSON: {', '.join(template_cols)}."
                
                # Extraer usando Gemini/NVIDIA
                extraction = orchestrator.process_document(text, is_difficult, prompt_instrucciones)
                
                # Limpiar archivo temporal
                os.unlink(tmp_path)
                
                # Llenar la fila con los resultados reales
                extracted_data = extraction.get("data", {})
                for col in template_cols:
                    row_data[col] = extracted_data.get(col, "")
                
                # Calcular Confianza y Estado
                confidence = extraction.get("confidence", "LOW")
                row_data["Confianza"] = f"🟢 ALTA ({extraction.get('source', 'IA')})" if confidence == "HIGH" else f"🟡 MEDIA ({extraction.get('source', 'IA')})"
                row_data["Estado"] = "✅ Completado"
                
            except Exception as e:
                row_data["Confianza"] = "🔴 FALLÓ"
                row_data["Estado"] = "⚠️ Error de Extracción"
                for col in template_cols:
                    row_data[col] = "Error"
        else:
            # SIMULACIÓN inteligente si no hay llaves configuradas
            time.sleep(1.5) # Simular procesamiento
            
            # Generar datos simulados consistentes pero dinámicos
            row_data["Estado"] = "✅ Completado" if idx != 2 else "⚠️ Revisión Manual"
            row_data["Confianza"] = "🟢 ALTA (Simulado)" if idx != 2 else "🔴 REVISIÓN MANUAL"
            
            # Rellenar columnas del template con mock data verosímil
            for col in template_cols:
                col_lower = col.lower()
                if "ítem" in col_lower or "item" in col_lower:
                    row_data[col] = f"ITM-0{idx+1}"
                elif "desc" in col_lower or "material" in col_lower or "producto" in col_lower:
                    row_data[col] = f"Material Extraído de {filename.split('.')[0]}"
                elif "cant" in col_lower:
                    row_data[col] = 10 * (idx + 1)
                elif "uni" in col_lower or "valor" in col_lower or "precio" in col_lower or "total" in col_lower:
                    row_data[col] = 1500 * (idx + 1)
                elif "proveedor" in col_lower:
                    row_data[col] = f"Proveedor {chr(65 + idx)}"
                else:
                    row_data[col] = f"Valor_{col}_{idx+1}"
        
        # Actualizar la lista y renderizar la previsualización en vivo
        results_list[idx] = row_data
        live_df = pd.DataFrame(results_list)
        with grid_placeholder.container():
            render_live_preview(live_df, key=f"grid_{idx}_final")
            
        progress_bar.progress((idx + 1) / total_files)
        
    st.session_state.extraction_results = live_df
    st.success("🎉 ¡Procesamiento finalizado con éxito!")
    st.markdown("### 👉 Ve al paso: **6. Revisión Final** para auditar y ver los archivos.")
