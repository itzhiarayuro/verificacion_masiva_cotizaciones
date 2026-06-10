# 🏢 Auditor de Cotizaciones V3

Automatiza la extracción de datos financieros de miles de cotizaciones en PDF o imágenes usando Inteligencia Artificial (Google Gemini + NVIDIA), y expórtalos a tu Excel en minutos.

## ✨ Características
- **Sin Límite de PDFs:** Arrastra cientos o miles (¡hasta 1M+!) vía Jobs + workers.
- **Integración de Email Real:** Gmail completo (paginación, miles de mensajes, mark-as-read, labels). Crea Jobs automáticamente. Notificaciones de salida (EmailSender).
- **Sistema de Jobs Escalable:** Persistencia (SQLAlchemy + SQLite/Postgres), Object Storage (local sharded o MinIO/S3), workers (simple DB-polling que funciona en Windows sin nada extra, o Celery+Redis).
- **Control de Costo LLM:** `llm_mode=none|fallback|always` por job + `AUDITOR_LLM_MODE=none`. 95%+ de PDFs se resuelven solo con tablas.
- **Optimización de Tokens:** Usa Microsoft MarkItDown para reducir el consumo de la IA hasta un 90%.
- **Cascada Resiliente:** MarkItDown -> pdfplumber -> OCR. Nunca se queda ciego ante un documento.
- **Equipo de 24 Agentes:** Visibilidad total (Senior Developer lidera). Logs por job.
- **Live Preview + API:** El modo pequeño sigue igual. API tiene endpoints `/jobs` y `/jobs/ingest-email`.
- **Resultados:** Parquet + CSV shards en storage (eficiente para millones de filas).

## 🚀 Instalación Rápida + Escala (1M PDFs)
1. Clona o descarga.
2. Windows: `install.bat` (o `.\venv\Scripts\python -m pip install -r requirements.txt` después de venv).
3. `python init_db.py`
4. **Para escala:** abre otra terminal y corre `python -m workers.simple_worker`
5. Ve a la **página 10 "Jobs + Email (Escala)"** en la UI, o usa la API (`/api/v1/jobs`, `/api/v1/jobs/ingest-email`).
6. (Recomendado) `docker compose up -d` para Redis + MinIO cuando vayas a producción.

El modo legacy (páginas 2-8, drag & drop pequeño) sigue funcionando exactamente igual para lotes interactivos.

## 🛠️ Stack Tecnológico
- **UI:** Streamlit (páginas 1-9 legacy + **página 10 "Jobs + Email (Escala)"**)
- **Backend:** Python 3.11+, FastAPI + SQLAlchemy
- **Escala:** JobManager + workers (simple_worker.py o Celery), Object Storage abstraction (Local / MinIO)
- **Modelos:** Gemini-2.0-Flash (Principal), Llama-3.1-70B vía NVIDIA NIM (Revisor) — controlado por llm_mode
- **Parseo:** MarkItDown, pdfplumber, pytesseract
- **Email:** Gmail API completo (lectura + envío + modify)

## 📖 Documentación Completa
- `specs/scaling_plan_v1.md` — Plan completo ejecutado (persistencia, workers, email real, reducción LLM, UI jobs).
- `specs/system_architecture.md` y `specs/workflow_rules.md`
- Corre `python -m workers.simple_worker --once` para procesar jobs pendientes.
- API docs en `/docs` cuando levantes `python run_api.py`.

**Para 1M PDFs (manejo robusto de errores en export):**
- `llm_mode="none"` + `low_memory=True` (por defecto en export)
- El export ahora recolecta errores **por shard**, escribe un `job_xxx_export_manifest.json` detallado, y **nunca falla el job completo**.
- Prefiere Parquet. Para jobs gigantes considera dividir por proveedor/fecha.
- Página 10 muestra errores de export + retry.
- Workers + `finalize_and_notify` tratan problemas de export como warnings.

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
