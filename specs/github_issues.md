# GitHub Issues - Formato Listo para Copiar

Este archivo contiene issues en formato Markdown que puedes copiar directamente a GitHub (usando "New issue" → pegar el contenido, o usar GitHub CLI).

---

## Issue #1: [Wave 1] Observabilidad básica para el sistema de Jobs

**Labels:** `wave-1`, `observability`, `core`, `high-priority`

**Domain:** Observability, Logging & Monitoring + Job System

### Descripción

Actualmente es muy difícil saber qué está pasando con un job grande. Necesitamos trazabilidad completa y métricas básicas.

### Tareas

- [ ] Implementar correlation ID por job (pasar a través de JobManager, workers, storage, email)
- [ ] Agregar logging estructurado (recomendado: structlog o logging con contexto)
- [ ] Exponer métricas básicas:
  - Jobs creados / procesados / fallidos
  - Filas extraídas por job
  - Tiempo promedio por documento
  - Errores por tipo
- [ ] Crear endpoint `/metrics` (JSON o Prometheus)
- [ ] Agregar logs de agente enriquecidos con job_id y correlation_id en `add_agent_log`

### Criterios de aceptación

- Cada job tiene un correlation ID visible en logs y en la UI.
- Puedo ver en logs el flujo completo de un job desde creación hasta finalización.
- Hay un endpoint que devuelve contadores básicos de actividad.

**Archivos clave:**
- `core/job_manager.py`
- `workers/simple_worker.py`
- `workers/tasks.py`
- `core/db.py`
- `api/main.py`
- Nuevo: `core/observability.py`

**Estimación:** 3-5 días

---

## Issue #2: [Wave 1] Robustez del Worker y Claiming de Jobs

**Labels:** `wave-1`, `workers`, `reliability`, `high-priority`

**Domain:** Job System & Worker Orchestration

### Descripción

El `simple_worker` actual puede causar duplicación de trabajo cuando se ejecutan múltiples instancias. Necesitamos claiming seguro y manejo de fallos robusto.

### Tareas

- [ ] Implementar claiming atómico de jobs (usar transacción + filtro de status + updated_at)
- [ ] Agregar campos a Job: `worker_id`, `last_heartbeat`, `claimed_at`
- [ ] Implementar heartbeat periódico desde el worker
- [ ] Mejorar `process_pending_jobs` para respetar heartbeats y timeouts
- [ ] Agregar método `reprocess_failed_documents(job_id)`
- [ ] Manejar graceful shutdown (señales SIGTERM/SIGINT)
- [ ] Marcar jobs como `failed` con mensaje de error claro cuando fallan consistentemente

### Criterios de aceptación

- Puedo ejecutar 3 workers en paralelo sin que procesen el mismo documento dos veces.
- Si mato un worker a la mitad de un documento, el documento queda como `failed` o `pending` (no `processing` para siempre).
- Existe forma de reintentar solo los documentos fallidos de un job.

**Archivos clave:**
- `core/job_manager.py`
- `core/db.py`
- `workers/simple_worker.py`
- `workers/tasks.py`
- `core/models.py` (extender Job)

**Estimación:** 5-7 días

---

## Issue #3: [Wave 1] Webhooks confiables con reintentos y firma

**Labels:** `wave-1`, `integrations`, `reliability`

**Domain:** External Integrations + API Layer

### Descripción

Los webhooks actuales son fire-and-forget. Necesitamos entregas confiables.

### Tareas

- [ ] Crear tabla `webhook_deliveries` (job_id, url, payload, status, attempts, last_error)
- [ ] Implementar `WebhookDeliveryService` con reintentos exponenciales
- [ ] Agregar firma HMAC en los headers (`X-Signature`)
- [ ] Modificar `finalize_and_notify` para encolar la entrega del webhook
- [ ] Exponer endpoint para reintentar manualmente un webhook fallido
- [ ] Logging de todos los intentos

### Criterios de aceptación

- Un webhook se reintenta al menos 5 veces con backoff.
- Todos los webhooks llevan firma verificable.
- Puedo ver el historial de entregas de un job.

**Archivos clave:**
- `core/db.py` + modelos
- Nuevo: `core/webhook_delivery.py`
- `api/main.py`
- `core/job_manager.py` / `core/db.py` (finalize_and_notify)

**Estimación:** 3-4 días

---

## Issue #4: [Wave 2] Dockerfile + docker-compose completo

**Labels:** `wave-2`, `deployment`, `ops`

**Domain:** Deployment, Infrastructure & Operations

### Descripción

No existe forma fácil de desplegar la aplicación completa con workers.

### Tareas

- [ ] Crear `Dockerfile` multi-stage (base + api + worker + ui)
- [ ] Reescribir `docker-compose.yml` para incluir:
  - api
  - streamlit
  - worker (puede escalarse)
  - redis
  - minio
  - (opcional) postgres
- [ ] Crear `entrypoint.sh` que ejecute `init_db.py` automáticamente
- [ ] Scripts de ayuda: `make up`, `make worker`, `make logs`
- [ ] Documentar variables de entorno requeridas en el compose

### Criterios de aceptación

- `docker compose up -d` levanta un entorno completo funcional.
- Puedo escalar workers con `docker compose up --scale worker=3`.
- El entorno usa las mismas variables que `.env.example`.

**Archivos clave:**
- `Dockerfile`
- `docker-compose.yml`
- `entrypoint.sh`
- `Makefile` o scripts en `scripts/`
- Actualizar `README.md`

**Estimación:** 4-5 días

---

## Issue #5: [Wave 2] Introducir Alembic para migraciones

**Labels:** `wave-2`, `database`, `ops`

**Domain:** Data Persistence & Models

### Descripción

Actualmente dependemos de `create_all()`. Esto no escala para cambios de esquema en producción.

### Tareas

- [ ] Instalar e inicializar Alembic
- [ ] Crear migración inicial que reproduzca el estado actual de los modelos
- [ ] Actualizar `init_db.py` para usar Alembic (o mantener create_all solo para tests/dev)
- [ ] Documentar cómo crear y aplicar migraciones
- [ ] Agregar verificación de versión de DB al startup de API y workers

### Criterios de aceptación

- Puedo hacer cambios en modelos y generar migraciones.
- El sistema arranca correctamente contra una base de datos existente después de aplicar migraciones.

**Archivos clave:**
- `alembic.ini`
- Carpeta `alembic/`
- `core/db.py`
- `core/models.py`
- `init_db.py`
- `README.md` y `specs/`

**Estimación:** 2-3 días

---

## Issue #6: [Wave 2] Configuración centralizada con pydantic-settings

**Labels:** `wave-2`, `config`, `dx`

**Domain:** Configuration, Secrets & Environment

### Descripción

Demasiados `os.getenv` dispersos. Esto genera errores de configuración difíciles de diagnosticar.

### Tareas

- [ ] Crear `core/config.py` usando `pydantic-settings`
- [ ] Definir modelo `Settings` con todos los valores actuales (DB, storage, LLM, email, celery, etc.)
- [ ] Reemplazar todos los `os.getenv` directos por imports de Settings
- [ ] Actualizar `.env.example` con todas las variables documentadas
- [ ] Validar configuración al startup

### Criterios de aceptación

- Toda la configuración vive en un solo lugar con tipos y validación.
- Si falta una variable crítica, falla rápido con mensaje claro.

**Archivos clave:**
- Nuevo: `core/config.py`
- Muchos archivos (`job_manager.py`, `db.py`, `storage/*`, `email_*`, `api/main.py`, `workers/*`, etc.)

**Estimación:** 3 días

---

## Issue #7: [Wave 3] Integrar ReconciliationEngine en el flujo de Jobs

**Labels:** `wave-3`, `business`, `high-value`

**Domain:** Business Logic: Reconciliation & Auditing

### Descripción

El motor de reconciliación existe pero no se usa en el sistema de jobs. Este es el valor principal del producto.

### Tareas

- [ ] Adaptar `ReconciliationEngine` para trabajar con resultados de un job (leyendo Parquet shards)
- [ ] Crear tabla `findings` o `job_findings`
- [ ] Ejecutar reconciliación automáticamente al finalizar un job (en `finalize_and_notify`)
- [ ] Exponer hallazgos en:
  - UI de jobs
  - Export consolidado (nueva columna o archivo separado)
  - API
- [ ] Agregar acción manual "Ejecutar reconciliación" en la UI

### Criterios de aceptación

- Al terminar un job, automáticamente se generan hallazgos de auditoría.
- Puedo ver los hallazgos desde la página de jobs.
- Los hallazgos se incluyen en el export consolidado.

**Archivos clave:**
- `core/reconciliation_engine.py`
- `core/job_manager.py`
- `core/db.py` + `core/models.py`
- `core/export.py`
- `ui/pages/09_jobs_y_email.py`
- `api/main.py`

**Estimación:** 6-8 días

---

## Issue #8: [Wave 3] Progreso en tiempo real y acciones por job en la UI

**Labels:** `wave-3`, `ui`, `ux`

**Domain:** Streamlit UI & User Experience

### Descripción

La experiencia actual de la página de jobs es muy estática. Necesitamos feedback en vivo y acciones útiles.

### Tareas

- [ ] Implementar progreso en vivo (usar `st.empty()` + polling cada 2-3s o Server-Sent Events si es posible)
- [ ] Mostrar lista de documentos por estado dentro de cada job
- [ ] Botones de acción: Reintentar fallidos, Exportar ahora, Enviar notificación, Ver hallazgos
- [ ] Vista de archivos en storage (con tamaño y links de descarga)
- [ ] Sección de "cola" (cuántos jobs pending/processing)

### Criterios de aceptación

- Mientras un worker procesa un job, veo el progreso actualizarse sin refrescar toda la página constantemente.
- Puedo actuar sobre un job directamente desde la interfaz.

**Archivos clave:**
- `ui/pages/09_jobs_y_email.py` (considerar renombrar)
- `core/job_manager.py`
- `core/db.py`
- `core/export.py`

**Estimación:** 5-7 días

---

## Issue #9: [Wave 1-2] Autenticación básica en la API y sistema de Jobs

**Labels:** `security`, `wave-1`, `wave-2`

**Domain:** Security & Access Control

### Descripción

Cualquiera puede crear y consultar jobs actualmente.

### Tareas (dividir en dos issues si es necesario)

- [ ] Implementar API Key simple (header `X-API-Key`)
- [ ] Middleware o dependencia de FastAPI que valide la key
- [ ] Agregar campo `api_key_id` o `owner` en el modelo Job
- [ ] Filtrar jobs por propietario en listados y acciones
- [ ] (Opcional Wave 2) Soporte básico de JWT

### Criterios de aceptación

- Endpoints de jobs requieren API Key válida.
- Un usuario solo puede ver y operar sus propios jobs (si implementamos ownership).

**Archivos clave:**
- `api/main.py`
- `core/db.py` + models
- `core/config.py`
- Nuevo: `api/dependencies.py` o `api/auth.py`

**Estimación:** 3-4 días

---

## Issue #10: [Wave 4] Consolidación de resultados sin cargar todo en memoria

**Labels:** `wave-4`, `performance`, `scale`

**Domain:** Scalability, Performance & Resilience + Storage

### Descripción

`export_consolidated` hace `pd.concat` de todos los shards. Esto falla con jobs muy grandes.

### Tareas

- [ ] Implementar consolidación usando `pyarrow.dataset` o lectura por chunks
- [ ] Escribir el consolidado de forma streaming cuando sea posible
- [ ] Soportar jobs de > 1M filas sin OOM
- [ ] Agregar opción de export particionado (por proveedor, por mes, etc.)

### Criterios de aceptación

- Puedo consolidar un job de 500k+ filas sin que el worker se quede sin memoria.
- El tiempo de export escala de forma razonable.

**Archivos clave:**
- `core/export.py`
- `core/job_manager.py`
- `core/storage/base.py` (posibles mejoras)

**Estimación:** 4-6 días

---

## Notas para el mantenedor

- Usa las labels `wave-1`, `wave-2`, `wave-3`, `wave-4` consistentemente.
- Vincula cada issue al dominio correspondiente en `specs/architecture_backlog_by_domains.md`.
- Marca el issue como "done" en el backlog cuando se complete.
- Prioriza los issues de Wave 1 antes de avanzar a Wave 2.

---

*Generado a partir del análisis completo de arquitectura.*