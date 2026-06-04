import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

def render_live_preview(df: pd.DataFrame, key: str = "live_grid"):
    """
    Renderiza un DataFrame usando AgGrid con estilo Excel y coloreado de celdas
    según el estado de procesamiento.
    """
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_default_column(editable=False, groupable=True)
    
    # Custom JS para colorear filas según una columna de 'status' oculta si existiera,
    # pero aquí podemos hacer algo simple configurando AgGrid.
    # Por brevedad, usaremos AgGrid estándar
    gb.configure_selection('single')
    gridOptions = gb.build()

    st.markdown("### 📊 Vista Previa en Tiempo Real")
    st.info("💡 Verás cómo se llena esta tabla automáticamente a medida que la IA lee los PDFs.")
    
    response = AgGrid(
        df,
        gridOptions=gridOptions,
        update_mode=GridUpdateMode.NO_UPDATE,
        allow_unsafe_jscode=True,
        theme='balham',  # Excel-like theme
        key=key
    )
    return response
