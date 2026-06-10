# Domain Deep Dives - Análisis Detallado de Dominios Críticos

Este documento expande con profundidad los dominios más importantes (especialmente los de Wave 1 y 2). Incluye:
- Análisis del estado actual
- Problemas específicos
- Diseño propuesto
- Tareas concretas
- Riesgos y consideraciones

---

## Dominio 1: Job System & Worker Orchestration (Máxima Prioridad)

### Estado Actual

- `JobManager` actúa como coordinador de alto nivel.
- `process_job_small_batch` es el entrypoint principal usado por workers.
- `simple_worker.py` hace polling simple con `list_jobs(status=None)`.
- No hay mecanismo de claiming atómico.
- Celery existe pero está infrautilizado (tarea de ingest incompleta).

### Problemas Detallados

1. **Race Condition en Claiming**
   - Dos workers pueden leer el mismo job como "pending" casi al mismo tiempo.
   - Ambos lo marcan como "processing".
   - Duplicación de procesamiento y posible corrupción de datos.

2. **Stuck Jobs**
   - Si un worker muere mientras procesa (crash, OOM, kill), el job queda en `processing` para siempre.
   - Solo se puede recuperar manualmente.

3. **Falta de Visibilidad de Workers**
   - No se sabe qué worker está procesando qué job.
   - No hay heartbeats.

4. **Reprocesamiento difícil**
   - No hay forma limpia de reintentar solo los documentos que fallaron en un job.

5. **Celery infrautilizado**
   - `workers/tasks.py` tiene una tarea de ingest que es placeholder.
   - No hay estrategia clara de cuándo usar Celery vs simple_worker.

### Diseño Propuesto

**Modelo Job (extensión):**
```python
class Job(Base):
    ...
    claimed_by: Mapped[Optional[str]] = mapped_column(String(100))
    claimed_at: Mapped[Optional[datetime]]
    last_heartbeat: Mapped[Optional[datetime]]
    failed_documents_count: Mapped[int] = mapped_column(Integer, default=0)
```

**Nueva lógica de claiming (en `core/db.py`):**
- Función `claim_next_job(worker_id: str) -> Optional[Job]`
- Usa transacción + subquery con LIMIT 1 + FOR UPDATE (en Postgres) o lógica de update returning (SQLite compatible).

**Heartbeat:**
- Los workers deben llamar `update_heartbeat(job_id, worker_id)` periódicamente.
- En el worker loop, si un job lleva mucho tiempo sin heartbeat → se puede liberar o marcar como failed.

**Reprocesamiento:**
- Nuevo método: `reprocess_failed_documents(job_id: str)`
- Filtra documentos con `status = 'failed'`
- Los vuelve a poner en `pending` y actualiza contadores.

**Estrategia Celery vs Simple:**
- Mantener simple_worker como "modo fácil" (sin Redis).
- Cuando Redis + Celery están disponibles → usar `enqueue_job_batch` con `.delay()`.

### Tareas Concretas (Priorizadas)

1. Extender modelo Job con campos de claiming y heartbeat.
2. Implementar `claim_next_job` + `update_heartbeat` en `core/db.py`.
3. Refactorizar `simple_worker.py` para usar claiming + heartbeat + shutdown graceful.
4. Agregar `reprocess_failed_documents` en JobManager + exponer en API y UI.
5. Mejorar detección de Celery en `job_manager.py` (ping real al broker).
6. (Opcional) Agregar campo `worker_type` (simple / celery) en el job para trazabilidad.

**Riesgos:**
- Cambios en claiming pueden romper jobs existentes en estado "processing".
- SQLite tiene limitaciones con locking comparado con Postgres.

---

## Dominio 2: Observability & Logging

### Estado Actual

- Uso básico de `logging.getLogger(__name__)`.
- `add_agent_log` guarda eventos como JSON en la columna `agent_logs` del Job.
- No hay propagation de contexto entre componentes.

### Problemas

- Imposible correlacionar logs de diferentes procesos (UI, API, worker, email).
- Cuando un job grande falla, es muy difícil reconstruir qué pasó.
- Métricas de negocio y operativas no existen.

### Diseño Propuesto

**Módulo central `core/observability.py`:**

```python
import contextvars
from typing import Optional

_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar("correlation_id", default=None)

def set_correlation_id(job_id: str):
    _correlation_id.set(job_id)

def get_correlation_id() -> Optional[str]:
    return _correlation_id.get()

def get_logger(name: str):
    # Retorna logger enriquecido con correlation_id
    ...
```

**Uso:**
- Al crear un job → `set_correlation_id(job.id)`
- En workers y tareas → recuperar del job y setearlo.
- En todos los logs importantes: `logger.info("Processing document", extra={"job_id": ..., "doc_id": ...})`

**Métricas:**
- Crear un endpoint simple o usar una clase `Metrics` con contadores en memoria (luego Prometheus).

### Tareas

1. Crear `core/observability.py` con ContextVar + logger helper.
2. Propagar correlation_id en:
   - Creación de jobs (API y UI)
   - JobManager
   - Workers (simple y Celery)
   - EmailSender / EmailIngest
   - Webhook delivery
3. Mejorar `add_agent_log` para aceptar correlation_id y más metadata.
4. Agregar endpoint `/api/v1/metrics` básico.
5. (Wave 2+) Integrar con Prometheus client.

---

## Dominio 3: Security & Access Control (Wave 1 + Wave 2)

### Estado Actual

- API completamente abierta.
- Cualquiera puede crear jobs, ver todos los jobs, y disparar procesamiento.

### Problemas

- Riesgo de abuso (alguien puede crear miles de jobs).
- No hay aislamiento entre diferentes usuarios/equipos.
- No hay forma de auditar quién hizo qué.

### Diseño Propuesto (Incremental)

**Fase Wave 1 (mínimo viable):**
- API Key simple (string configurada en `.env` o por cliente).
- Header: `X-API-Key`
- Middleware/dependency en FastAPI que valide la key.
- Jobs se crean con `created_by_api_key` (o `owner`).

**Fase Wave 2 (mejor):**
- Soporte para múltiples API Keys (tabla `api_keys`).
- Cada key tiene permisos básicos (read, write, admin).
- Jobs tienen `owner_id`.

**Fase Wave 3+:**
- JWT + usuarios
- Multi-tenancy real (organizaciones)

### Tareas Recomendadas

1. Crear Settings para `API_KEYS` (lista de keys válidas o una master key).
2. Dependency de FastAPI `get_current_api_key()`.
3. Proteger todos los endpoints de `/api/v1/jobs*`.
4. Agregar columna `created_by` en el modelo Job.
5. Filtrar listados de jobs por el owner de la key (cuando haya múltiples keys).

**Consideraciones:**
- Mantener compatibilidad con el modo Streamlit local (puede usar una key "local" o bypass en desarrollo).

---

## Dominio 4: Webhook Delivery (Wave 1)

### Estado Actual

```python
# api/webhooks.py
def send_webhook(url: str, payload: Dict):
    requests.post(url, json=payload, timeout=10)
```

### Problemas

- Si falla → se pierde para siempre.
- No hay firma → cualquiera puede enviar payloads falsos al destino.
- No hay visibilidad de si se entregó o no.

### Diseño Propuesto

1. Nueva tabla `webhook_deliveries`:
   - id, job_id, url, payload (json), status (pending/success/failed), attempts, last_error, next_retry_at

2. Servicio `WebhookDeliveryService`:
   - `enqueue(job, webhook_url)`
   - `deliver(delivery_id)` con reintentos
   - Backoff: 30s, 2min, 10min, 1h, etc.

3. Firma:
   - `X-Signature: sha256=<hex>`
   - Secreto compartido (por job o global).

4. Worker o tarea Celery que procese la cola de webhooks pendientes.

### Tareas

- Crear modelo y migración.
- Implementar servicio de delivery.
- Modificar `finalize_and_notify`.
- Agregar reintento manual en API/UI.
- Documentar cómo verificar la firma en el lado del consumidor.

---

## Dominio 5: Reconciliation & Business Auditing (Wave 3 - Alto Valor)

### Estado Actual

- `ReconciliationEngine` + `ProviderIdentifier` existen y tienen lógica.
- Se usan principalmente en el flujo legacy (páginas antiguas).
- No están conectados al sistema de jobs + Parquet.

### Oportunidad

Este es uno de los diferenciadores más grandes del producto: "auditoría real de precios cruzando múltiples cotizaciones".

### Diseño Propuesto

1. Adaptar `ReconciliationEngine` para recibir un job_id o lista de DataFrames de resultados.
2. Ejecutarlo después de la consolidación (o sobre los shards).
3. Persistir hallazgos:
   - Tabla `findings` con: job_id, item_key, severidad, tipo, descripción, evidencia.
4. Exponer:
   - En UI de jobs (expanders por hallazgo)
   - En export consolidado (columnas extra o archivo `findings.parquet`)
   - En API

### Tareas de alto nivel

- Refactor ligero de `ReconciliationEngine` para modo "job".
- Nueva tabla + modelo.
- Integración en `finalize_and_notify` (después del export).
- UI + API para consultar hallazgos.
- (Opcional) Reglas configurables por proveedor.

---

## Resumen de Prioridad de Dominios para Implementación

1. **Job System & Worker Orchestration** ← Empezar aquí YA
2. **Observability** ← Empezar en paralelo (bajo riesgo, alto valor para debugging)
3. **Webhook Delivery**
4. **Security (API Key básica)**
5. **Deployment (Docker)**
6. **Reconciliation** (después de tener base sólida)

---

*Documento generado como parte de la solicitud A+B+C+D.*