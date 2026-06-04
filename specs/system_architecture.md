# System Architecture

## Visión General
El Auditor de Cotizaciones V3 es una herramienta orientada a automatizar la extracción de datos financieros desde cotizaciones en PDF y correos electrónicos, utilizando extracción en cascada (MarkItDown -> pdfplumber -> OCR) y validación cruzada con modelos de lenguaje (Gemini para extracción primaria, NVIDIA para revisión). 

## Componentes Principales
1. **Capa de Presentación (UI)**: Streamlit para interfaz web.
2. **Procesamiento de Documentos**: `markitdown` como motor principal de tokenización.
3. **Orquestador LLM**: Integración dual LLM.
4. **Capa de Datos**: `pandas` y `openpyxl` para manejo de Excel.
5. **Capa de Integración**: OAuth2 para emails, FastAPI para endpoints REST.

## Convenciones
- Nomenclatura en Python: `snake_case` para variables y funciones, `PascalCase` para clases.
- Errores y Excepciones: Uso de clases personalizadas para errores de rate limit y fallos de extracción.
- Estado de la UI: Guardado en `outputs/session_state.json`.
