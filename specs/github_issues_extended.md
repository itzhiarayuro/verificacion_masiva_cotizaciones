# GitHub Issues Adicionales (Wave 1 + Wave 2)

Estos son issues complementarios a los 10 del archivo `github_issues.md`. Formato listo para copiar.

---

## Issue #11: [Wave 1] Graceful Shutdown en Workers

**Labels:** `wave-1`, `workers`, `reliability`

**Descripción:**
Los workers actuales no manejan señales de terminación. Si se mata el proceso, los jobs pueden quedar en estado inconsistente.

**Tareas:**
- [ ] Capturar SIGTERM y SIGINT en `simple_worker.py`
- [ ] Terminar el batch actual de forma limpia antes de salir
- [ ] Liberar el claim del job actual si es posible
- [ ] Hacer lo mismo en las tareas de Celery (usar `task_time_limit` + señales)
- [ ] Agregar logs claros de "shutting down gracefully"

**Archivos clave:** `workers/simple_worker.py`, `workers/tasks.py`

**Estimación:** 2 días

---

## Issue #12: [Wave 1] Detección real de disponibilidad de Celery

**Labels:** `wave-1`, `workers`, `celery`

**Descripción:**
La función `is_celery_available()` solo intenta importar redis. No valida que el broker esté realmente disponible.

**Tareas:**
- [ ] Mejorar `is_celery_available()` para hacer un ping real al broker Redis
- [ ] Cachear el resultado por unos minutos
- [ ] Usar esta detección también en la UI de jobs (mostrar si Celery está disponible)
- [ ] Documentar la diferencia entre modo "simple_worker" y "Celery"

**Archivos clave:** `core/job_manager.py`, `workers/celery_app.py`

**Estimación:** 1-2 días

---

## Issue #13: [Wave 1] Endpoint para reintentar documentos fallidos de un job

**Labels:** `wave-1`, `api`, `jobs`

**Descripción:**
Necesitamos exponer la capacidad de re-procesar documentos fallidos vía API (para que la UI y herramientas externas lo usen).

**Tareas:**
- [ ] Agregar endpoint `POST /api/v1/jobs/{job_id}/reprocess-failed`
- [ ] Llamar al nuevo método `reprocess_failed_documents` en JobManager
- [ ] Devolver lista de documentos que se pusieron en pending nuevamente
- [ ] Agregar validación de que el job esté en estado completed/partial/failed

**Archivos clave:** `api/main.py`, `core/job_manager.py`

**Estimación:** 2 días

---

## Issue #14: [Wave 2] Soporte para Postgres en docker-compose

**Labels:** `wave-2`, `deployment`, `database`

**Descripción:**
Actualmente el compose solo tiene comentarios sobre Postgres. Hay que hacerlo funcional.

**Tareas:**
- [ ] Descomentar y configurar el servicio `postgres` en docker-compose.yml
- [ ] Agregar healthcheck
- [ ] Actualizar variables de ejemplo (`DATABASE_URL`)
- [ ] Hacer que la aplicación use Postgres cuando `DATABASE_URL` esté definida
- [ ] Documentar cómo cambiar de SQLite a Postgres

**Archivos clave:** `docker-compose.yml`, `README.md`, `.env.example`

**Estimación:** 2 días

---

## Issue #15: [Wave 2] Rate Limiting en la API

**Labels:** `wave-2`, `security`, `api`

**Descripción:**
La API de jobs puede ser abusada fácilmente (creación masiva de jobs).

**Tareas:**
- [ ] Integrar `slowapi` o `fastapi-limiter` (con Redis si está disponible)
- [ ] Definir límites por API Key (ej: 10 jobs por minuto, 100 requests/min)
- [ ] Aplicar límites en endpoints de creación de jobs y de ingesta de email
- [ ] Devolver headers de rate limit (`X-RateLimit-Remaining`, etc.)

**Archivos clave:** `api/main.py`, `core/config.py`

**Estimación:** 3 días

---

## Issue #16: [Wave 2] Validación estricta de tamaño de uploads

**Labels:** `wave-2`, `security`, `api`

**Descripción:**
No hay límites en el tamaño de los PDFs que se pueden subir a través de la API o la UI de jobs. Esto puede causar OOM.

**Tareas:**
- [ ] Definir límites en Settings: `MAX_PDF_SIZE_MB`, `MAX_JOB_TOTAL_SIZE_MB`
- [ ] Validar tamaño en el endpoint de creación de jobs (antes de escribir a storage)
- [ ] Validar también en la página de jobs de Streamlit
- [ ] Devolver error claro cuando se excede el límite

**Archivos clave:** `api/main.py`, `ui/pages/09_jobs_y_email.py`, `core/config.py`

**Estimación:** 2 días

---

## Issue #17: [Wave 2] Healthchecks y Readiness probes ricos

**Labels:** `wave-2`, `ops`, `deployment`

**Descripción:**
El endpoint `/health` actual es muy básico. Necesitamos distinguir entre "la app está viva" y "la app está lista para recibir tráfico".

**Tareas:**
- [ ] Mejorar `/health` (liveness): responde rápido, solo verifica que el proceso esté vivo
- [ ] Crear `/ready` (readiness): verifica DB, storage, Redis (si aplica), etc.
- [ ] Incluir versión de la app y commit (si está disponible)
- [ ] Usar estos endpoints en docker-compose healthchecks y en Kubernetes (cuando llegue el momento)

**Archivos clave:** `api/main.py`

**Estimación:** 2 días

---

## Issue #18: [Wave 1] Mejorar `add_agent_log` y exponer logs por job en API

**Labels:** `wave-1`, `observability`, `api`

**Descripción:**
Los agent_logs actuales son útiles pero limitados. Queremos poder consultarlos de forma estructurada.

**Tareas:**
- [ ] Mejorar la estructura de los logs guardados (timestamp, agent_id, level, message, metadata)
- [ ] Agregar endpoint `GET /api/v1/jobs/{job_id}/logs`
- [ ] Soportar filtros básicos (limit, since, agent)
- [ ] Usar esto en la UI de jobs para mostrar actividad reciente

**Archivos clave:** `core/db.py`, `api/main.py`, `ui/pages/09_jobs_y_email.py`

**Estimación:** 2-3 días

---

## Issue #19: [Wave 2] Centralizar y mejorar el manejo de errores en JobManager

**Labels:** `wave-2`, `reliability`, `core`

**Descripción:**
Actualmente hay muchos `try/except` dispersos con manejo inconsistente.

**Tareas:**
- [ ] Crear excepciones personalizadas en `core/exceptions.py` (JobNotFound, DocumentProcessingError, StorageError, etc.)
- [ ] Unificar el manejo de errores en `process_document` y `process_job_small_batch`
- [ ] Asegurar que los errores se guarden correctamente en el documento y en el job
- [ ] Loggear con correlation_id siempre que sea posible

**Archivos clave:** `core/job_manager.py`, nuevo `core/exceptions.py`

**Estimación:** 3 días

---

## Issue #20: [Wave 2] Soporte para múltiples API Keys + tabla de keys

**Labels:** `wave-2`, `security`

**Descripción:**
Pasar de una sola API Key hardcodeada a un sistema de múltiples keys administrables.

**Tareas:**
- [ ] Crear modelo `ApiKey`
- [ ] Endpoint para crear/revocar keys (protegido por master key)
- [ ] Almacenar hash de la key (no la key en claro)
- [ ] Asociar jobs a la key que los creó
- [ ] Filtrar listados de jobs según la key autenticada

**Archivos clave:** `core/models.py`, `core/db.py`, `api/main.py`

**Estimación:** 4-5 días

---

## Issue #21: [Wave 1] Documentar estrategia "Simple Worker vs Celery"

**Labels:** `wave-1`, `documentation`, `workers`

**Descripción:**
Hay confusión sobre cuándo usar cada modo de worker.

**Tareas:**
- [ ] Actualizar README con una sección clara "Modos de ejecución de Workers"
- [ ] Crear tabla comparativa (requisitos, escalabilidad, facilidad de uso)
- [ ] Agregar recomendaciones en `specs/roadmap_waves.md` y en la UI de jobs
- [ ] Incluir comandos exactos para ambos modos

**Archivos clave:** `README.md`, `ui/pages/09_jobs_y_email.py` (sección de instrucciones), `specs/`

**Estimación:** 1 día

---

## Issue #22: [Wave 2] Integrar Celery Beat para ingesta programada de email

**Labels:** `wave-2`, `integrations`, `celery`

**Descripción:**
La ingesta de Gmail es manual actualmente. Queremos poder programarla.

**Tareas:**
- [ ] Configurar Celery Beat en `workers/celery_app.py`
- [ ] Crear tarea periódica (ej. cada hora) que llame a `ingest_gmail_to_job` con queries configurables
- [ ] Permitir configurar las queries vía variables de entorno o una tabla simple
- [ ] Documentar cómo activar Beat

**Archivos clave:** `workers/celery_app.py`, `workers/tasks.py`, `core/email_ingest.py`

**Estimación:** 3-4 días

---

## Notas

- Estos issues están priorizados para Wave 1 y Wave 2.
- Muchos dependen de que se resuelvan primero los issues de claiming y observabilidad.
- Se recomienda vincularlos al backlog principal en `specs/architecture_backlog_by_domains.md`.

---

*Generado como extensión del trabajo A+B+C+D.*