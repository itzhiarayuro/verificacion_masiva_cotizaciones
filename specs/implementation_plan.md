# Plan de Implementación Detallado

**Versión:** 1.0  
**Basado en:** Análisis exhaustivo de `specs/architecture_backlog_by_domains.md` + Roadmap por Waves

Este documento da el **orden concreto** de implementación, con archivos específicos a tocar en cada paso.

---

## Principios de Implementación

1. **Nunca romper el camino actual.** El modo legacy (páginas 2-9) y el simple_worker deben seguir funcionando mientras se construye lo nuevo.
2. **Entregar valor incremental.** Cada wave debe poder demostrarse con jobs reales.
3. **Documentar mientras se avanza.** Actualizar el backlog y este plan conforme se complete cada item.
4. **Tests primero en partes críticas** (especialmente claiming de workers y finalize logic).

---

## Fase / Wave 1: Fundamentos de Confiabilidad

### 1.1 Observabilidad Básica (Hacer primero)

**Orden de trabajo:**

1. Crear `core/observability.py`
   - Implementar `get_correlation_id()` y `set_correlation_id(job_id)`
   - Helper para logging con contexto

2. Modificar `core/db.py`
   - Actualizar `add_agent_log` para aceptar y guardar `correlation_id`
   - Agregar campo `correlation_id` al modelo Job (o usarlo como job_id que ya es único)

3. Modificar `core/job_manager.py`
   - En `create_upload_job` y `create_email_ingest_job`: generar correlation_id
   - Pasar correlation_id a todas las llamadas de logging y workers

4. Actualizar `workers/simple_worker.py` y `workers/tasks.py`
   - Propagar correlation_id en logs y llamadas a JobManager

5. Actualizar `api/main.py`
   - Generar correlation_id en endpoints de creación de jobs
   - Inyectarlo en el contexto

6. Agregar endpoint simple de métricas en `api/main.py`:
   ```python
   @app.get("/api/v1/metrics")
   async def metrics():
       # Contar jobs por status, filas totales, etc.
   ```

**Entregable de esta subfase:**
- Puedo correr un job y seguir todo el rastro en los logs usando el job_id.

### 1.2 Robustez del Worker (Crítico)

**Orden de trabajo:**

1. Actualizar `core/models.py`
   - Agregar a Job:
     - `claimed_by: str | None`
     - `claimed_at: datetime | None`
     - `last_heartbeat: datetime | None`
     - `failed_documents_count: int = 0`

2. En `core/db.py`:
   - Crear función `claim_next_job(worker_id: str)` que haga un update atómico:
     ```sql
     UPDATE jobs SET status='processing', claimed_by=?, claimed_at=now()
     WHERE id = (SELECT id FROM jobs WHERE status IN ('pending','partial') ORDER BY created_at LIMIT 1)
     RETURNING *
     ```
   - Crear `update_heartbeat(job_id, worker_id)`
   - Mejorar `finalize_job_if_complete`

3. Refactorizar `workers/simple_worker.py`:
   - Usar la nueva función de claim
   - Implementar loop de heartbeat cada 15-30 segundos
   - Manejar señales para graceful shutdown
   - Implementar `reprocess_failed_documents(job_id)`

4. Actualizar `core/job_manager.py`:
   - Agregar método `reprocess_failed_documents(job_id)`
   - Mejorar manejo de excepciones en `process_document`

**Entregable:**
- Puedo lanzar `python -m workers.simple_worker` en 3 terminales diferentes y procesar jobs sin duplicados.

### 1.3 Webhooks Confiables (Paralelo a 1.2)

1. Crear modelo `WebhookDelivery` en `core/models.py`
2. Crear `core/webhook_delivery.py` con la lógica de reintentos
3. Modificar `finalize_and_notify` para encolar la entrega
4. Agregar firma HMAC
5. Exponer en API botón/endpoint para reintentar

---

## Wave 2: Producción Readiness

### 2.1 Deployment (Empezar temprano en la wave)

**Orden recomendado:**

1. Crear `Dockerfile` (multi-stage recomendado)
   - Stage base con dependencias
   - Stage para API
   - Stage para Streamlit
   - Stage para Worker

2. Reescribir `docker-compose.yml`:
   - Servicios: `api`, `ui`, `worker`, `redis`, `minio`, `db` (postgres opcional)
   - Volúmenes para storage y outputs
   - Healthchecks
   - Variables de entorno desde `.env`

3. Crear `entrypoint.sh`:
   ```bash
   python init_db.py
   exec "$@"
   ```

4. Crear scripts de conveniencia (`scripts/start_worker.sh`, etc.)

5. Actualizar `install.sh` / `install.bat` y README.

### 2.2 Alembic + Configuración

1. Inicializar Alembic (`alembic init`)
2. Configurar `alembic/env.py` para usar los modelos de `core/models.py`
3. Generar migración inicial
4. Crear `core/config.py` con pydantic-settings
5. Reemplazar `os.getenv` en todo el código (empezar por los más críticos: db, storage, celery, llm keys)

### 2.3 Seguridad Básica

1. En `api/main.py`:
   - Agregar dependencia de API Key
   - Configurar en Settings

2. Extender modelo Job con `owner_id` o `api_key_hash`

3. Filtrar consultas por propietario donde corresponda

---

## Wave 3: Valor de Negocio

### 3.1 Integración de Reconciliación (Más alto valor)

**Orden de trabajo:**

1. Revisar y adaptar `core/reconciliation_engine.py` para aceptar resultados de jobs (DataFrame o lista de shards)

2. Crear modelo `Finding` en `core/models.py`

3. En `core/job_manager.py` o nuevo módulo `core/audit.py`:
   - Función `run_reconciliation_for_job(job_id)`

4. Llamar a esta función desde `finalize_and_notify` (después del export)

5. Exponer en:
   - `ui/pages/09_jobs_y_email.py`
   - API
   - Export (agregar columna `audit_status` o archivo separado de hallazgos)

### 3.2 Mejoras de UI de Jobs

Hacer esto **después** de tener reconciliación funcionando.

- Implementar componente de progreso en vivo
- Lista de documentos con estados
- Acciones por job (reintentar fallidos, ver hallazgos, etc.)

---

## Wave 4: Escala (Solo después de tener volumen real)

- Refactor de `core/export.py` para streaming
- Soporte avanzado de MinIO/S3 (multipart, lifecycle)
- Métricas + Prometheus + Grafana
- Orquestación real con Celery + múltiples colas
- Multi-tenancy

---

## Matriz de Archivos por Wave (Resumen)

| Archivo / Módulo                    | Wave 1 | Wave 2 | Wave 3 | Wave 4 | Notas |
|-------------------------------------|--------|--------|--------|--------|-------|
| `core/job_manager.py`               | ★★★    | ★      | ★★     | ★      | Muy tocado |
| `core/db.py` + `core/models.py`     | ★★★    | ★★     | ★★     | ★      | Migraciones + nuevos modelos |
| `workers/simple_worker.py`          | ★★★★   | ★      | -      | ★      | Prioridad máxima |
| `workers/tasks.py` + `celery_app.py`| ★★     | ★★     | -      | ★★     | - |
| `core/storage/*`                    | ★      | ★      | -      | ★★★    | Mejoras en Wave 4 |
| `core/reconciliation_engine.py`     | -      | -      | ★★★★   | -      | Integración clave |
| `core/export.py`                    | -      | -      | ★★     | ★★★    | Performance en Wave 4 |
| `api/main.py`                       | ★★     | ★★★    | ★      | -      | Auth + rate limit |
| `ui/pages/09_jobs_y_email.py`       | ★      | -      | ★★★★   | -      | Gran trabajo en Wave 3 |
| `Dockerfile` + `docker-compose.yml` | -      | ★★★★   | -      | -      | - |
| `core/config.py` (nuevo)            | -      | ★★★★   | -      | -      | - |
| `alembic/`                          | -      | ★★★★   | -      | -      | - |
| `core/observability.py` (nuevo)     | ★★★★   | -      | -      | ★      | - |
| `core/webhook_delivery.py` (nuevo)  | ★★★    | -      | -      | -      | - |

---

## Checklist por Wave (para tracking)

### Wave 1 - Confiabilidad
- [ ] Observabilidad + correlation ID
- [ ] Claiming seguro + heartbeats en workers
- [ ] Re-procesamiento de documentos fallidos
- [ ] Graceful shutdown
- [ ] Webhooks con reintentos y firma
- [ ] Auth básica (API Key)
- [ ] Métricas básicas

### Wave 2 - Producción
- [ ] Dockerfile + docker-compose completo
- [ ] Alembic + primera migración
- [ ] Configuración centralizada (pydantic-settings)
- [ ] Rate limiting
- [ ] Healthchecks ricos
- [ ] Ingesta programada de email (Celery Beat)
- [ ] Mejor EmailSender (adjuntos)

### Wave 3 - Valor
- [ ] ReconciliationEngine integrado en jobs
- [ ] Hallazgos persistidos y visibles
- [ ] UI de jobs con acciones y progreso en vivo
- [ ] Human review básico para documentos fallidos
- [ ] Cost tracking básico

### Wave 4 - Escala
- [ ] Export streaming / sin OOM
- [ ] Soporte completo MinIO/S3 en todos los flujos
- [ ] Métricas + Prometheus/Grafana
- [ ] Orquestación avanzada de workers
- [ ] Multi-tenancy ligero

---

## Recomendaciones Prácticas

- **Haz commits pequeños** por sub-tarea (ej: "feat: add correlation_id to jobs").
- **Actualiza** `specs/architecture_backlog_by_domains.md` marcando los items completados.
- **Prueba siempre** con jobs reales de varios PDFs después de cada wave.
- **No hagas Wave 3 completo** hasta tener Wave 1 + 2 estables. Es fácil perder tiempo en UI bonita si el backend no es confiable.

---

**Siguiente paso recomendado:**
Empezar por **1.1 Observabilidad** + **1.2 Robustez del Worker** en paralelo (dos personas o un desarrollador alternando).

---

*Plan generado a partir del análisis completo de la arquitectura actual.*