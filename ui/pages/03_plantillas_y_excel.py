import streamlit as st
import os

st.title("📊 3. Tu Archivo Excel")
st.markdown("¿En qué formato quieres consolidar la información?")

tab1, tab2 = st.tabs(["⬇️ Usar una Plantilla (Recomendado)", "📁 Subir mi propio Excel"])

with tab1:
    st.markdown("Selecciona uno de nuestros formatos probados. Si usas uno de estos, el sistema pre-configurará el mapeo por ti.")
    
    plantilla_seleccionada = st.radio(
        "Escoge tu industria:",
        ["🏗️ Obra Civil (Ideal para materiales de construcción)", 
         "🚜 Alquiler Equipos (Ideal para maquinaria pesada)", 
         "⚡ Material Eléctrico (Ideal para fichas técnicas)"]
    )
    
    st.session_state.plantilla = plantilla_seleccionada
    
    # Crear estructura visual según la selección
    import pandas as pd
    if "Obra Civil" in plantilla_seleccionada:
        df = pd.DataFrame(columns=["Ítem", "Descripción_Material", "Unidad", "Cantidad", "Valor_Unitario", "Valor_Total", "Proveedor"])
    elif "Alquiler Equipos" in plantilla_seleccionada:
        df = pd.DataFrame(columns=["Ítem", "Tipo_Equipo", "Horas_Mes", "Valor_Hora", "Valor_Total", "Proveedor"])
    else:
        df = pd.DataFrame(columns=["Ítem", "Referencia_Eléctrica", "Marca_Sugerida", "Cantidad", "Valor_Unitario", "Proveedor"])

    st.markdown("### 👁️ Vista Previa y Personalización")
    st.info("💡 **TIP:** Puedes agregar filas, eliminar columnas o cambiarles el nombre directamente aquí. Lo que dejes en esta tabla será la estructura final de tu Excel.")
    
    # Renderizar tabla editable (añade filas dinámicamente si el usuario quiere)
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, key="template_editor")
    
    # Guardar la estructura personalizada en sesión
    st.session_state.custom_template_df = edited_df
    st.success(f"Estructura guardada temporalmente. ¡Lista para usar!")

with tab2:
    st.markdown("Arrastra aquí tu propio archivo de Excel vacío (o con datos previos).")
    uploaded_excel = st.file_uploader("Sube tu archivo .xlsx", type=["xlsx"])
    if uploaded_excel:
        st.success("Excel cargado correctamente.")
        st.session_state.custom_excel = uploaded_excel.name
        st.info("Como es un Excel propio, por favor ve al Paso 4 para decirle a la IA qué es cada columna.")

st.divider()
st.markdown("### 👉 Ve al paso: **4. Mapeo de Columnas** (Si subiste Excel propio) o **5. Procesamiento** (Si usas plantilla)")
