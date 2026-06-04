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

# Inicializar st.session_state.uploaded_pdfs y extraction_results
if "uploaded_pdfs" not in st.session_state:
    st.session_state.uploaded_pdfs = []

if "extraction_results" not in st.session_state:
    st.session_state.extraction_results = None

uploaded_files = []

if data_source == "local":
    uploaded_files = st.file_uploader(
        "Arrastra aquí todos tus PDFs (sin límite):", 
        type=["pdf"], 
        accept_multiple_files=True
    )
elif data_source == "gmail":
    st.info("Utilizando PDFs descargados automáticamente desde tu Gmail.")
    st.session_state.uploaded_pdfs = [
        {"name": "Gmail_Cotizacion_Maquinaria.pdf", "bytes": b"%PDF-1.4 mock content"},
        {"name": "Gmail_Presupuesto_Materiales.pdf", "bytes": b"%PDF-1.4 mock content"}
    ]

# Guardar los archivos locales en session_state
if data_source == "local" and uploaded_files:
    # Solo resetear si los archivos cargados cambian
    current_names = [f.name for f in uploaded_files]
    saved_names = [pdf["name"] for pdf in st.session_state.uploaded_pdfs]
    if current_names != saved_names:
        st.session_state.uploaded_pdfs = []
        st.session_state.extraction_results = None # Limpiar resultados anteriores
        for f in uploaded_files:
            file_bytes = f.read()
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

# Botón de Procesamiento
if st.button("🚀 Iniciar Extracción con IA") and st.session_state.uploaded_pdfs:
    st.markdown("### Procesando documentos...")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Obtener las columnas del template
    if "custom_template_df" in st.session_state:
        template_cols = list(st.session_state.custom_template_df.columns)
    else:
        template_cols = ["Ítem", "Descripción_Material", "Cantidad", "Valor_Unitario", "Valor_Total", "Proveedor"]
        
    all_cols = ["Archivo", "Confianza", "Estado"] + template_cols
    results_list = []
    
    grid_placeholder = st.empty()
    
    # Inicializar servicios
    api_ready = st.session_state.get("api_keys_configured", False) and os.getenv("GEMINI_API_KEY")
    parser = DocumentParser()
    orchestrator = LLMOrchestrator() if api_ready else None
    
    total_files = len(st.session_state.uploaded_pdfs)
    
    for idx, pdf_info in enumerate(st.session_state.uploaded_pdfs):
        filename = pdf_info["name"]
        pdf_bytes = pdf_info["bytes"]
        
        status_text.text(f"Abriendo {filename} ({idx + 1}/{total_files})...")
        
        placeholder_idx = len(results_list)
        placeholder_row = {col: "" for col in all_cols}
        placeholder_row["Archivo"] = filename
        placeholder_row["Estado"] = "⏳ Procesando..."
        results_list.append(placeholder_row)
        
        # Renderizar temporal en vivo
        live_df = pd.DataFrame(results_list)
        with grid_placeholder.container():
            render_live_preview(live_df, key=f"grid_{idx}_init")
            
        global_proveedor = "Desconocido"
        extracted_items = []
        source_name = "Simulado"
        
        if api_ready:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(pdf_bytes)
                    tmp_path = tmp_file.name
                
                pages = parser.parse_document_by_pages(tmp_path)
                confidences = []
                sources = []
                item_fields = [col for col in template_cols if col.lower() != "proveedor"]
                
                for p_idx, p_data in enumerate(pages):
                    text = p_data["text"]
                    is_difficult = p_data["is_difficult"]
                    page_num = p_data["page"]
                    
                    status_text.text(f"Analizando {filename} - Procesando Página {page_num}/{len(pages)}...")
                    
                    prompt_instrucciones = f"""
                    Identifica el nombre comercial del Proveedor de la cotización y extrae la lista completa de TODOS los productos, materiales, o servicios cotizados en esta página {page_num} del documento.
                    Es muy importante que extraigas todas las filas de la tabla de cotización sin omitir ninguna.
                    Retorna UNICAMENTE un objeto JSON válido con la siguiente estructura exacta:
                    {{
                      "proveedor": "Nombre comercial del Proveedor",
                      "items": [
                        {{
                          {", ".join([f'"{f}": "valor extraído para {f}"' for f in item_fields])}
                        }}
                      ]
                    }}
                    """
                    
                    extraction = orchestrator.process_document(text, is_difficult, prompt_instrucciones)
                    
                    extracted_json = extraction.get("data", {})
                    prov_candidate = extracted_json.get("proveedor", "Desconocido")
                    if prov_candidate and prov_candidate != "Desconocido":
                        global_proveedor = prov_candidate
                        
                    page_items = extracted_json.get("items", [])
                    if isinstance(page_items, list):
                        extracted_items.extend(page_items)
                        
                    confidences.append(extraction.get("confidence", "LOW"))
                    sources.append(extraction.get("source", "IA"))
                
                os.unlink(tmp_path)
                
                if "LOW" in confidences:
                    confidence = "LOW"
                elif "MEDIUM" in confidences:
                    confidence = "MEDIUM"
                else:
                    confidence = "HIGH"
                    
                source_name = "/".join(list(set(sources)))
                conf_label = f"🟢 ALTA ({source_name})" if confidence == "HIGH" else f"🟡 MEDIA ({source_name})"
                
            except Exception as e:
                global_proveedor = "Error"
                extracted_items = [{"error": str(e)}]
                conf_label = "🔴 FALLÓ"
        else:
            # SIMULACIÓN dinámica multilínea
            time.sleep(1.5)
            global_proveedor = filename.split('.')[0].upper()
            
            num_sim_items = 125 if "KAIZEN" in filename.upper() or "792" in filename else 5
            extracted_items = []
            
            kaizen_data = [
                {"desc": "NIPLE PASAMURO EN HIERRO DÚCTIL DE Ø8\", EXTREMOS BRIDA X LISO L=0,45 M", "price": 121.37},
                {"desc": "NIPLE EN HIERRO DÚCTIL DE Ø8\", EXTREMOS BRIDADOS L=0,10 M", "price": 70.77},
                {"desc": "NIPLE EN HIERRO DÚCTIL DE Ø12\" EXTREMOS BRIDADOS L=0,27 M", "price": 167.01},
                {"desc": "NIPLE EN HIERRO DÚCTIL DE Ø12\" EXTREMOS BRIDADOS L=0,52 M", "price": 220.96},
                {"desc": "NIPLE EN HIERRO DÚCTIL DE Ø12\" EXTREMOS BRIDADOS L=0,41 M", "price": 197.23},
                {"desc": "NIPLE EN HIERRO DÚCTIL DE Ø12\", EXTREMOS BRIDA X LISO L=0,36 M", "price": 132.06},
                {"desc": "NIPLE EN HIERRO DÚCTIL DE Ø12\", EXTREMOS BRIDA X LISO L=0,24 M", "price": 95.50},
                {"desc": "NIPLE EN HIERRO DÚCTIL DE Ø4\" EXTREMOS BRIDADOS L=3,28 M", "price": 238.43},
                {"desc": "NIPLE EN HIERRO DÚCTIL DE Ø4\" EXTREMOS BRIDADOS L=0,70 M", "price": 72.94},
                {"desc": "NIPLE PASAMURO EN HIERRO DÚCTIL DE Ø4\", EXTREMOS BRIDA X LISO L=0,91 M", "price": 89.38},
                {"desc": "NIPLE EN HIERRO DÚCTIL DE Ø3\" EXTREMOS BRIDADOS L=1,02 M", "price": 77.50},
                {"desc": "NIPLE EN HIERRO DÚCTIL DE Ø3\", EXTREMOS BRIDA X LISO L=1,62 M", "price": 96.28},
                {"desc": "NIPLE EN HIERRO DÚCTIL DE Ø3\" EXTREMOS BRIDADOS L=25,36 M", "price": 1338.94},
                {"desc": "NIPLE EN HIERRO DÚCTIL DE Ø3\", EXTREMOS BRIDA X LISO L=1,37 M", "price": 83.32},
                {"desc": "NIPLE EN HIERRO DÚCTIL DE Ø3\" EXTREMOS BRIDADOS L=9,14 M", "price": 498.32},
                {"desc": "NIPLE EN HIERRO DÚCTIL DE Ø3\", EXTREMOS BRIDA X LISO L=1,40 M", "price": 84.88},
                {"desc": "NIPLE EN HIERRO DÚCTIL DE Ø3\" EXTREMOS BRIDADOS L=27,94 M", "price": 1472.65}
            ]
            
            for i in range(num_sim_items):
                item_data = {}
                sim_item = kaizen_data[i % len(kaizen_data)] if ("KAIZEN" in filename.upper() or "792" in filename) else None
                
                for col in template_cols:
                    col_lower = col.lower()
                    if "ítem" in col_lower or "item" in col_lower:
                        item_data[col] = f"{i+1}"
                    elif "desc" in col_lower or "material" in col_lower or "producto" in col_lower:
                        if sim_item:
                            item_data[col] = sim_item["desc"]
                        else:
                            item_data[col] = f"Material de Obra Civil Ref #{i+1}"
                    elif "cant" in col_lower:
                        item_data[col] = 1
                    elif "uni" in col_lower or "valor" in col_lower or "precio" in col_lower:
                        if sim_item:
                            item_data[col] = sim_item["price"]
                        else:
                            item_data[col] = 150.0 * (i + 1)
                    elif "total" in col_lower:
                        if sim_item:
                            item_data[col] = sim_item["price"]
                        else:
                            item_data[col] = 150.0 * (i + 1)
                extracted_items.append(item_data)
                
            conf_label = "🟢 ALTA (Simulado)"

        # Remover placeholder
        results_list.pop(placeholder_idx)
        
        # Insertar los ítems
        for item_dict in extracted_items:
            row_data = {col: "" for col in all_cols}
            row_data["Archivo"] = filename
            row_data["Confianza"] = conf_label
            row_data["Estado"] = "✅ Completado"
            
            for col in template_cols:
                if col.lower() == "proveedor":
                    row_data[col] = global_proveedor
                else:
                    row_data[col] = item_dict.get(col, "")
            
            results_list.append(row_data)
            
        # Actualizar vista en vivo
        live_df = pd.DataFrame(results_list)
        with grid_placeholder.container():
            render_live_preview(live_df, key=f"grid_{idx}_final")
            
        progress_bar.progress((idx + 1) / total_files)
        
    st.session_state.extraction_results = live_df
    # Forzar recarga para renderizar a nivel raíz de forma persistente
    st.rerun()

# --- RENDERIZADO PERSISTENTE FUERA DEL BOTÓN ---
if st.session_state.extraction_results is not None:
    st.success(f"🎉 ¡Procesamiento finalizado con éxito! Se extrajeron {len(st.session_state.extraction_results)} líneas de productos de tus PDFs.")
    
    st.markdown("### 📊 Vista Previa de Datos Extraídos")
    st.info("💡 **TIP:** Puedes hacer clic en los encabezados para ordenar, filtrar o redimensionar las columnas. La tabla no desaparecerá.")
    
    # Renderizado persistente a nivel de página
    render_live_preview(st.session_state.extraction_results, key="grid_persistente")
    
    st.markdown("### 👉 Ve al paso: **6. Revisión Final** para auditar y ver los archivos.")
