# 🏢 Auditor de Cotizaciones V3

Automatiza la extracción de datos financieros de miles de cotizaciones en PDF o imágenes usando Inteligencia Artificial (Google Gemini + NVIDIA), y expórtalos a tu Excel en minutos.

## ✨ Características
- **Sin Límite de PDFs:** Arrastra cientos o miles de archivos a la vez.
- **Integración de Email:** Conecta tu Gmail o Outlook y la app buscará adjuntos automáticamente.
- **Optimización de Tokens:** Usa Microsoft MarkItDown para reducir el consumo de la IA hasta un 90%.
- **Cascada Resiliente:** MarkItDown -> pdfplumber -> OCR. Nunca se queda ciego ante un documento.
- **Doble LLM:** Extrae con Gemini (rápido/barato) y revisa casos difíciles con NVIDIA (Llama 3.1 70B).
- **Live Preview:** Mira cómo tu Excel se llena celda por celda en tiempo real.
- **API REST:** Conecta tu ERP o CRM directamente.

## 🚀 Instalación Rápida (1 clic)
1. Clona o descarga este repositorio.
2. En Windows: Haz doble clic en `install.bat`.
3. En Mac/Linux: Ejecuta `./install.sh`.
4. El navegador se abrirá automáticamente en la pantalla de bienvenida.

## 🛠️ Stack Tecnológico
- **UI:** Streamlit
- **Backend:** Python 3.11+, FastAPI
- **Modelos:** Gemini-2.0-Flash (Principal), Llama-3.1-70B vía NVIDIA NIM (Revisor)
- **Parseo:** MarkItDown, pdfplumber, pytesseract

## 📖 Documentación Completa
Revisa la carpeta `specs/` para ver la arquitectura detallada (Spec-Driven Development).

## 🧪 Tests
Se incluye una suite de tests reales (pytest):

- `tests/test_live_qa.py` — QA en tiempo real
- `tests/test_table_extractor.py`, `test_metadata_extractor.py`, `test_pdf_pipeline.py`
- `tests/test_agents.py` — 24 agentes + orquestador
- `tests/test_reconciliation.py` — Motor de auditoría de precios
- `tests/test_integration_real_pdf.py` — Integración con PDFs reales del proyecto (usa `temp_pdf_viewer/KAIZEN.pdf`)

**Ejecutar tests:**
- Windows: `run_tests.bat`
- Linux/Mac: `./run_tests.sh`

O manualmente:
```bash
python -m pytest tests/ -q
```

Los tests funcionan sin claves de API (usan `use_llm=False` donde es posible). Los tests de integración marcados con `@pytest.mark.integration` se saltan si no encuentran los PDFs de ejemplo.
