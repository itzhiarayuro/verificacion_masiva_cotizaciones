# Roadmap por Oleadas (Waves) - Auditor de Cotizaciones

**Objetivo:** Llevar el sistema actual a un estado **producción-ready** para procesamiento masivo confiable, con dependencias claras.

**Criterios de priorización:**
- Impacto en estabilidad y confiabilidad (no romperse con jobs grandes)
- Riesgo de pérdida de datos o trabajos fallidos
- Facilidad de adopción (mantener camino simple actual funcionando)
- Valor de negocio (reconciliación + auditoría)

---

## Wave 0 — Ya entregado (Baseline actual)
- Nueva arquitectura `core/` + JobManager + workers
- Sistema de jobs con Parquet shards + export consolidado
- Ingesta real de Gmail + EmailSender
- Storage abstraction (local + MinIO)
- Página 10 de Jobs + Email
- API de jobs básica
- Tests en extracción legacy

---

## Wave 1: Fundamentos de Confiabilidad (Must have para no romperse)
**Duración estimada:** 2-3 semanas  
**Objetivo:** Hacer que el sistema de jobs sea usable en producción sin miedo a pérdida de trabajos o estados inconsistentes.

### Items principales (orden recomendado dentro de la wave)

1. **Observabilidad básica**
   - Logging estructurado (structlog o logging con correlation_id)
   - Correlation ID por job que atraviese UI → API → Worker → Storage → Email
   - Métricas básicas en JobManager y workers (jobs procesados, filas, errores, duración)
   - Exposición de métricas (Prometheus endpoint o endpoint JSON simple)

2. **Robustez del Worker**
   - Mejor claiming de jobs (usar `status='pending'` + update atómico o row-level lock)
   - Heartbeat / lease por worker (última vez visto)
   - Manejo correcto de errores + reintentos por documento
   - Soporte básico de re-procesamiento de documentos fallidos (nuevo método en JobManager + endpoint/UI)
   - Graceful shutdown en `simple_worker.py` y tareas Celery

3. **Mejoras en resiliencia del JobManager**
   - Mejor manejo de excepciones en `process_document` y `process_job_small_batch`
   - Idempotencia en escritura de resultados (evitar duplicados si se re-procesa)
   - DLQ simple (jobs en estado `failed` con razón clara + documentos fallidos marcados)

4. **Webhooks confiables (mínimo)**
   - Cola de entrega de webhooks (usar la misma DB o tabla dedicada)
   - Reintentos exponenciales + backoff
   - Firma HMAC básica
   - Registro de intentos de entrega

5. **Autenticación básica (skeleton)**
   - API Key simple para la API (header `X-API-Key`)
   - Protección mínima en endpoints de jobs
   - (Opcional) ownership básico de jobs (user_id o api_key_id)

**Dependencias:** Ninguna fuerte dentro de Wave 1. Se puede atacar en paralelo Observabilidad + Worker robustness.

**Archivos clave a tocar:**
- `core/job_manager.py`
- `workers/simple_worker.py`
- `workers/tasks.py`
- `core/db.py` (nuevos campos: last_heartbeat, failed_documents_count, etc.)
- `api/main.py`
- Nuevo: `core/observability.py` o `core/logging.py`
- Nuevo: `core/webhook_delivery.py`
- `specs/architecture_backlog_by_domains.md` (marcar items completados)

**Criterio de salida de Wave 1:**
- Puedo lanzar 3 workers simples en paralelo sin que se dupliquen jobs.
- Si un worker muere, el job no queda atascado para siempre.
- Tengo trazabilidad completa de un job desde creación hasta finalización.
- Webhooks se reintentan al menos 5 veces.

---

## Wave 2: Producción Readiness & Operabilidad
**Duración estimada:** 3-4 semanas  
**Objetivo:** Poder desplegar y operar el sistema de forma profesional.

### Items principales

1. **Deployment & Docker**
   - Dockerfile multi-stage para la app (Streamlit + FastAPI + workers)
   - `docker-compose.yml` completo que levante: app, api, worker(s), redis, minio (y opcional postgres)
   - Scripts de entrada (`entrypoint.sh`) que corran `init_db.py` automáticamente
   - Soporte para múltiples workers (compose profiles o escalado)

2. **Migraciones de base de datos**
   - Introducir Alembic
   - Primera migración (crear todas las tablas actuales)
   - Script de upgrade/downgrade

3. **Configuración centralizada**
   - Adoptar `pydantic-settings` (o pydantic v2 Settings)
   - Modelo `Settings` con validación
   - `.env.example` muy completo y documentado
   - Separación clara dev / prod

4. **Mejoras de seguridad**
   - Auth más robusta (API Key + JWT opcional)
   - Rate limiting básico (slowapi o similar en FastAPI)
   - Validación estricta de uploads (tamaño máximo por archivo y por job)
   - Sanitización mejorada de nombres de archivo

5. **Completar integraciones críticas**
   - Hacer que la ingesta periódica de email funcione (Celery Beat + tarea real)
   - Mejorar `EmailSender` (adjuntos pequeños, HTML básico)
   - Outlook como stub documentado claramente con pasos para implementarlo

6. **Healthchecks y operaciones**
   - Endpoints `/health`, `/ready`, `/metrics` ricos
   - Soporte para graceful shutdown en API
   - Monitoreo básico de workers desde la UI de jobs (último heartbeat)

**Dependencias:** 
- Wave 1 (especialmente Observabilidad y Worker robustness) es prerrequisito fuerte.
- Auth básica de Wave 1 se puede extender aquí.

**Archivos clave:**
- `Dockerfile`
- `docker-compose.yml` (reescritura)
- `entrypoint.sh` / `run_worker.sh`
- `alembic.ini` + carpeta `alembic/`
- `core/config.py` (nuevo)
- `api/main.py` (agregar rate limit, auth middleware)
- `workers/celery_app.py` (configurar beat)
- Nuevo worker entrypoint

**Criterio de salida de Wave 2:**
- Puedo hacer `docker compose up` y tener un entorno completo funcionando.
- Puedo cambiar de SQLite a Postgres sin perder datos (vía migraciones).
- La aplicación puede recibir API keys y rechaza requests sin ellas.
- Puedo programar ingesta de email automáticamente.

---

## Wave 3: Valor de Negocio & Experiencia de Usuario
**Duración estimada:** 3-4 semanas  
**Objetivo:** Que el sistema entregue el valor real por el que se creó (auditoría + reconciliación masiva).

### Items principales

1. **Integración de Reconciliation**
   - Cablear `ReconciliationEngine` al final de un job (o como paso post-procesamiento)
   - Persistir hallazgos (nueva tabla `findings` o en el job)
   - Exponer hallazgos en la UI de jobs y en export

2. **Human-in-the-Loop para Jobs**
   - Página o sección para revisar documentos fallidos o ítems dudosos
   - Capacidad de corregir / aprobar manualmente a nivel de documento o ítem
   - Marcar documentos para re-procesamiento con LLM forzado

3. **Mejora grande de la UI de Jobs (Página 10)**
   - Progreso en tiempo real (SSE o polling inteligente + st.empty)
   - Vista de documentos por estado (pending / processing / completed / failed)
   - Botones de acción por job: "Exportar ahora", "Reintentar fallidos", "Enviar email", "Ver hallazgos"
   - Lista de archivos en storage (shards + consolidados) con links de descarga
   - Estimación de costo/tiempo (básica)

4. **Cost Tracking**
   - Registrar tokens estimados + reales por documento/job
   - Dashboard simple de costos por proveedor o por período

5. **Mejor soporte de export**
   - Streaming / chunked consolidation para jobs muy grandes (evitar OOM)
   - Export a DuckDB / Parquet dataset particionado (opcional)
   - Integración con el motor de reconciliación en el export consolidado

**Dependencias fuertes:**
- Wave 1 y Wave 2 completas (necesitas workers confiables y deployment antes de invertir en UX de negocio).
- Buen estado de la base de datos (migraciones).

**Archivos clave:**
- `core/reconciliation_engine.py` (adaptar para jobs)
- Nuevo: `core/findings.py` o extender modelos
- `ui/pages/09_jobs_y_email.py` (o renombrar a `10_jobs.py`)
- `core/job_manager.py` (agregar pasos post-procesamiento)
- `core/export.py` (mejorar para grandes volúmenes)
- `api/main.py` (endpoints de findings y acciones)

**Criterio de salida de Wave 3:**
- Al terminar un job grande, obtengo automáticamente hallazgos de reconciliación.
- Puedo revisar y corregir documentos fallidos desde la interfaz.
- El progreso del job se actualiza sin tener que refrescar manualmente todo el tiempo.

---

## Wave 4: Escala Avanzada & Madurez
**Duración estimada:** 4+ semanas  
**Objetivo:** Preparar el sistema para volúmenes reales de 500k – varios millones de filas de forma eficiente y observable.

### Items principales

1. **Performance & Eficiencia**
   - Consolidación de resultados con pyarrow.dataset o streaming (sin cargar todo en pandas)
   - Paralelismo dentro de un worker (procesar varios documentos en paralelo con threads/processes limitados)
   - Caché de resultados intermedios (Redis)
   - Mejor particionado de storage por job

2. **Orquestación avanzada de workers**
   - Soporte real para múltiples workers Celery con colas diferentes
   - Auto-scaling básico (usando Celery o scripts externos)
   - Priorización y fair scheduling

3. **Almacenamiento y retención**
   - Lifecycle policies (borrado automático de jobs antiguos)
   - Soporte completo para MinIO/S3 en todos los flujos (incluyendo export grande)
   - Compresión y formato columnar optimizado

4. **Observabilidad avanzada**
   - Integración con Prometheus + Grafana (o similar)
   - Tracing distribuido (OpenTelemetry)
   - Dashboards operativos reales

5. **Multi-tenancy ligero**
   - Jobs pertenecen a organizaciones/usuarios
   - Aislamiento de datos y permisos
   - Facturación / cuotas por tenant (opcional)

6. **Completar integraciones**
   - Implementación real de Outlook
   - Soporte para más fuentes (carpetas compartidas, SFTP, etc.)

**Dependencias:**
- Todo lo anterior. Esta wave solo tiene sentido cuando ya estás usando el sistema en producción con volumen real.

---

## Resumen de Dependencias entre Waves

```
Wave 1 (Confiabilidad)
    ├── Observabilidad básica
    ├── Worker robustness
    └── Webhooks + Auth skeleton
            │
            ▼
Wave 2 (Producción)
    ├── Docker + Compose completo
    ├── Alembic
    ├── Config centralizada
    └── Seguridad + Operaciones
            │
            ▼
Wave 3 (Valor de Negocio)
    ├── Reconciliation integrado
    ├── Human-in-the-loop
    └── UI de jobs madura + Cost tracking
            │
            ▼
Wave 4 (Escala Avanzada)
    ├── Performance a gran escala
    ├── Orquestación multi-worker avanzada
    └── Multi-tenancy + Observabilidad full
```

---

## Recomendación de Ejecución

- **No saltes Wave 1.** Es la más importante para que el trabajo que ya hiciste no se pierda.
- Haz **Wave 1 + Wave 2** antes de invertir mucho en UX bonita (Wave 3).
- Usa el archivo `specs/architecture_backlog_by_domains.md` como fuente de verdad y ve marcando items conforme avances.
- Cada wave debería terminar con una demostración concreta (poder procesar 500+ PDFs reales de extremo a extremo de forma confiable).

---

*Documento generado automáticamente basado en el análisis exhaustivo de gaps.*