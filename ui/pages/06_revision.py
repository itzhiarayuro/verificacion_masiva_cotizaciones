import streamlit as st
import pandas as pd
import tempfile
import os
import sys
from pathlib import Path

# Añadir el path raíz para importar módulos locales
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from core.document_parser import DocumentParser
from core.llm_orchestrator import LLMOrchestrator

st.title("✅ 6. Revisión Final (Human-in-the-loop)")
st.markdown("Revisa los datos antes de exportarlos a tu Excel final. Si algo está mal, corrígelo directamente en la tabla o abajo inspeccionando el PDF original.")

# Verificar si hay resultados de extracción en la sesión
if "extraction_results" not in st.session_state or st.session_state.extraction_results.empty:
    st.warning("⚠️ No se ha procesado ningún documento todavía. Ve al paso **5. Procesamiento** e inicia la extracción.")
else:
    # 1. Tabla general editable
    st.markdown("### 📊 Tabla General de Resultados Extraídos")
    st.info("Puedes hacer doble clic en cualquier celda para corregir los valores manualmente.")
    
    # Mostrar la tabla como editable y guardar los cambios del usuario en el session_state
    edited_df = st.data_editor(
        st.session_state.extraction_results,
        disabled=["Archivo", "Confianza", "Estado"],
        hide_index=True,
        use_container_width=True,
        key="global_results_editor"
    )
    st.session_state.extraction_results = edited_df
    
    st.divider()
    
    # 2. Vista individual con visor de PDF
    st.markdown("### 🔎 Inspeccionar Documento Individual y Corregir")
    
    pdf_list = st.session_state.get("uploaded_pdfs", [])
    if pdf_list:
        pdf_names = [pdf["name"] for pdf in pdf_list]
        selected_pdf_name = st.selectbox("Selecciona un PDF para visualizarlo y ver sus datos:", pdf_names)
        
        # Encontrar los bytes del PDF seleccionado
        selected_pdf = next(p for p in pdf_list if p["name"] == selected_pdf_name)
        
        # Encontrar la fila correspondiente en el DataFrame de resultados
        df_idx = st.session_state.extraction_results[st.session_state.extraction_results["Archivo"] == selected_pdf_name].index
        
        if len(df_idx) > 0:
            idx = df_idx[0]
            
            # Columnas de diseño: PDF a la izquierda, formulario a la derecha
            col1, col2 = st.columns([3, 2])
            
            with col1:
                st.markdown(f"📄 **Visor del Documento: {selected_pdf_name}**")
                
                # Guardar el PDF temporalmente en disco para renderizarlo
                tmp_dir = Path("./temp_pdf_viewer")
                tmp_dir.mkdir(exist_ok=True)
                tmp_pdf_path = tmp_dir / selected_pdf_name
                
                with open(tmp_pdf_path, "wb") as f:
                    f.write(selected_pdf["bytes"])
                
                # Intentar renderizar el PDF usando streamlit-pdf-viewer
                try:
                    from streamlit_pdf_viewer import pdf_viewer
                    pdf_viewer(str(tmp_pdf_path))
                except Exception as e:
                    # Fallback si falla el plugin
                    st.error(f"No se pudo cargar el visor de PDF: {e}")
                    st.info("Puedes descargar el archivo temporal aquí:")
                    st.download_button(
                        label="Descargar PDF para ver localmente",
                        data=selected_pdf["bytes"],
                        file_name=selected_pdf_name,
                        mime="application/pdf"
                    )
            
            with col2:
                st.markdown("📝 **Valores Extraídos y Corrección**")
                
                # Mostrar los datos de las columnas del template
                # Identificar cuáles columnas no son de control
                non_control_cols = [c for c in st.session_state.extraction_results.columns if c not in ["Archivo", "Confianza", "Estado"]]
                
                # Crear inputs para cada columna
                updated_values = {}
                for col in non_control_cols:
                    current_val = st.session_state.extraction_results.at[idx, col]
                    # Convertir a string para el text_input
                    new_val = st.text_input(f"Campo: {col}", value=str(current_val))
                    updated_values[col] = new_val
                
                if st.button("💾 Guardar Cambios Manuales"):
                    for col, val in updated_values.items():
                        st.session_state.extraction_results.at[idx, col] = val
                    st.success("¡Valores actualizados! Se reflejarán en el reporte final.")
                    st.rerun()
                
                st.divider()
                
                st.markdown("🤖 **Reintentar Extracción Inteligente**")
                pista = st.text_area("Dale una pista a la IA para reintentar (Ej: 'El precio total está abajo a la derecha'):")
                
                if st.button("🔄 Re-extraer con Pista"):
                    api_ready = st.session_state.get("api_keys_configured", False) and os.getenv("GEMINI_API_KEY")
                    
                    with st.spinner("Re-procesando con la pista..."):
                        if api_ready:
                            try:
                                parser = DocumentParser()
                                orchestrator = LLMOrchestrator()
                                
                                parse_res = parser.parse_document(str(tmp_pdf_path))
                                text = parse_res.get("text", "")
                                is_difficult = parse_res.get("is_difficult", False)
                                
                                instructions = f"Extrae los siguientes campos: {', '.join(non_control_cols)}. Pista adicional: {pista}."
                                
                                extraction = orchestrator.process_document(text, is_difficult, instructions)
                                extracted_data = extraction.get("data", {})
                                
                                # Actualizar la fila en el DataFrame
                                for col in non_control_cols:
                                    st.session_state.extraction_results.at[idx, col] = extracted_data.get(col, "")
                                
                                st.session_state.extraction_results.at[idx, "Confianza"] = f"🟢 ALTA (Re-extraído)"
                                st.session_state.extraction_results.at[idx, "Estado"] = "✅ Completado"
                                st.success("¡Extracción exitosa con la pista!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al re-procesar con la IA: {e}")
                        else:
                            # Simulación de re-extracción si no hay llaves
                            time_delay = 1.5
                            import time
                            time.sleep(time_delay)
                            
                            # Simular que con la pista se resolvió la duda
                            for col in non_control_cols:
                                if "valor" in col.lower() or "precio" in col.lower() or "total" in col.lower():
                                    st.session_state.extraction_results.at[idx, col] = "99999" # Cambiar a un valor simulado
                            
                            st.session_state.extraction_results.at[idx, "Confianza"] = "🟢 ALTA (Simulado con Pista)"
                            st.session_state.extraction_results.at[idx, "Estado"] = "✅ Completado"
                            st.success("¡Re-extracción simulada con éxito usando tu pista!")
                            st.rerun()
        else:
            st.error("No se encontró el registro de datos para este archivo.")
    else:
        st.info("No hay PDFs guardados en la sesión para visualizar.")

st.divider()
st.markdown("### 👉 Ve al último paso: **7. Exportar**")
