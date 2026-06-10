# Estado Actual vs Estado Deseado por Wave

Este documento compara el **estado actual** del sistema con el **estado deseado** para cada Wave. Sirve como referencia rápida de progreso y para definir "Definition of Done" por oleada.

---

## Wave 1: Fundamentos de Confiabilidad

### 1.1 Observabilidad Básica

| Aspecto                    | Estado Actual                                      | Estado Deseado (fin de Wave 1)                          | Gap Principal |
|---------------------------|----------------------------------------------------|---------------------------------------------------------|---------------|
| Correlation ID            | No existe                                          | Todo log y evento tiene job_id / correlation_id traceable | No hay mecanismo de contexto |
| Logging                   | `logging` estándar disperso                        | Logging estructurado con contexto (job, worker, doc)   | Sin estructura ni contexto |
| Métricas                  | Ninguna                                            | Endpoint `/metrics` con contadores básicos             | No hay exposición de métricas |
| Agent Logs                | JSON blob truncado a ~80 eventos en la tabla Job   | Logs enriquecidos y consultables                       | Truncado y no estructurado |
| Trazabilidad end-to-end   | Imposible seguir un job completo                   | Se puede seguir un job desde creación hasta email/webhook | Sin propagation |

### 1.2 Robustez del Worker

| Aspecto                    | Estado Actual                                      | Estado Deseado                                          | Gap Principal |
|---------------------------|----------------------------------------------------|---------------------------------------------------------|---------------|
| Claiming de jobs          | `list_jobs()` + marcar processing (race condition) | Claim atómico con `claimed_by` + `claimed_at`          | Alta probabilidad de duplicados |
| Heartbeat / Lease         | No existe                                          | Workers reportan heartbeat cada 15-30s                 | Jobs se quedan en "processing" si worker muere |
| Manejo de fallos          | Marca documento como failed, pero poco más         | Re-procesamiento selectivo de documentos fallidos      | No hay forma fácil de reintentar solo fallidos |
| Graceful Shutdown         | No implementado                                    | Worker termina batch actual y libera recursos limpiamente | Riesgo de corrupción de estado |
| Múltiples workers         | Peligroso (duplicación)                            | Seguro correr 3+ workers en paralelo                   | No usable en producción con concurrencia |

### 1.3 Webhooks Confiables

| Aspecto                    | Estado Actual                  | Estado Deseado                              | Gap |
|---------------------------|--------------------------------|---------------------------------------------|-----|
| Entrega                   | Fire-and-forget (`requests.post`) | Reintentos con backoff exponencial         | Sin resiliencia |
| Firma de seguridad        | Ninguna                        | HMAC en header (`X-Signature`)             | Inseguro |
| Historial de entregas     | No se registra                 | Tabla `webhook_deliveries` con intentos    | Cero visibilidad |
| Reintento manual          | No existe                      | Endpoint / botón para reintentar           | - |

### 1.4 Autenticación Básica

| Aspecto                    | Estado Actual | Estado Deseado                     | Gap |
|---------------------------|---------------|------------------------------------|-----|
| Protección de API         | Ninguna       | API Key obligatoria (header)       | Totalmente abierto |
| Ownership de jobs         | No existe     | Jobs asociados a una API Key       | Cualquiera ve todo |

**Criterio de salida Wave 1:**
- Puedo correr 3 workers sin duplicar trabajo.
- Tengo trazabilidad completa de un job en logs.
- Webhooks se reintentan y llevan firma.
- La API requiere key básica.

---

## Wave 2: Producción Readiness

### Deployment & Operaciones

| Aspecto                    | Estado Actual                          | Estado Deseado                              |
|---------------------------|----------------------------------------|---------------------------------------------|
| Docker para la app        | No existe                              | Dockerfile multi-stage + entrypoint         |
| docker-compose            | Solo Redis + MinIO                     | Entorno completo (API + UI + Worker + infra) |
| Migraciones               | `create_all()`                         | Alembic con migraciones versionadas         |
| Configuración             | `os.getenv` disperso                   | `pydantic-settings` centralizado            |
| Healthchecks              | Endpoint muy básico                    | `/health`, `/ready`, `/metrics` ricos       |
| Ingesta programada        | Mencionada pero no implementada        | Celery Beat funcionando                     |

### Seguridad

| Aspecto                    | Estado Actual | Estado Deseado                          |
|---------------------------|---------------|-----------------------------------------|
| Rate limiting             | No            | Básico en FastAPI                       |
| Validación de uploads     | Débil         | Límites de tamaño por archivo y job     |
| Secrets                   | Archivos + .env | Mejor manejo + documentación            |

**Criterio de salida Wave 2:**
- `docker compose up` levanta todo el entorno.
- Se pueden aplicar migraciones de esquema.
- La aplicación está protegida con API Key y rate limiting.

---

## Wave 3: Valor de Negocio

### Reconciliación & Auditoría

| Aspecto                    | Estado Actual                          | Estado Deseado                                      |
|---------------------------|----------------------------------------|-----------------------------------------------------|
| ReconciliationEngine      | Existe pero aislado (modo legacy)      | Se ejecuta automáticamente al finalizar jobs      |
| Hallazgos                 | Se generan en memoria                  | Persistidos en tabla `findings` + visibles en UI  |
| Integración en jobs       | Ninguna                                | Hallazgos disponibles en export y página de jobs  |

### Experiencia en Jobs (UI)

| Aspecto                    | Estado Actual             | Estado Deseado                                      |
|---------------------------|---------------------------|-----------------------------------------------------|
| Progreso                  | Solo polling manual       | Actualización en vivo (SSE o polling inteligente)  |
| Acciones por job          | Muy limitadas             | Reintentar fallidos, ver hallazgos, exportar, etc. |
| Visibilidad de documentos | Básica                    | Lista por estado + preview de shards               |
| Human-in-the-loop         | Solo en flujo legacy      | Revisión y corrección de documentos fallidos       |

**Criterio de salida Wave 3:**
- Al terminar un job grande obtengo hallazgos de reconciliación automáticamente.
- Puedo operar y revisar jobs de forma cómoda desde la interfaz.

---

## Wave 4: Escala Avanzada

| Aspecto                    | Estado Actual                     | Estado Deseado                                      |
|---------------------------|-----------------------------------|-----------------------------------------------------|
| Export de resultados      | `pd.concat` en memoria            | Streaming / pyarrow.dataset (sin OOM)              |
| Almacenamiento            | Local + MinIO básico              | Lifecycle policies, multipart, múltiples backends  |
| Orquestación de workers   | Simple worker + Celery básico     | Múltiples colas, auto-scaling, fair scheduling     |
| Observabilidad full       | Logs + métricas básicas           | Prometheus + Grafana + OpenTelemetry tracing       |
| Multi-tenancy             | No existe                         | Jobs pertenecen a tenants + aislamiento            |

---

## Cómo usar este documento

- Marca las filas conforme avances.
- Usa la columna "Gap Principal" para definir las tareas de cada issue.
- Al final de cada Wave, revisa si se cumplen los **Criterios de salida** antes de pasar a la siguiente.

---

*Generado como parte de la planificación completa A+B+C+D.*