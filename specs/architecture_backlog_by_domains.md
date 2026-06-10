# Backlog de Arquitectura - Auditor de Cotizaciones
## Organizado por Dominios (Análisis exhaustivo)

**Fecha del análisis:** Actual (post-refactor core/jobs + workers)  
**Alcance:** Revisión completa de gaps, deuda técnica, stubs, limitaciones y piezas faltantes (sin filtrar por prioridad).

---

## 1. Job System & Worker Orchestration

- **Claiming de jobs inseguro en simple_worker**: Usa `list_jobs` + update. Múltiples workers pueden procesar el mismo job simultáneamente.
- **Falta de distributed locking o lease mechanism**: No hay `SELECT FOR UPDATE`, advisory locks, ni heartbeats para workers.
- **Tarea de Celery incompleta**: `ingest_email_and_create_job` en `workers/tasks.py` es un placeholder ("not_fully_wired_yet").
- **Sin Dead Letter Queue (DLQ)**: Los jobs o documentos que fallan repetidamente no tienen destino claro.
- **Re-procesamiento granular ausente**: No hay forma fácil de reintentar solo documentos fallidos de un job desde UI o API.
- **Workers sin graceful shutdown**: No manejan SIGTERM / SIGINT de forma limpia (pueden dejar jobs en estado inconsistente).
- **Sin heartbeats ni visibilidad de workers**: No se sabe qué workers están vivos ni qué jobs están siendo procesados activamente.
- **Detección de Celery frágil**: `is_celery_available()` solo intenta importar redis; no valida conectividad real al broker.
- **Falta de colas y prioridades**: Todo va a la misma cola. No hay separación entre jobs urgentes y masivos.
- **Falta de control de concurrencia de jobs**: No hay límite de jobs "processing" simultáneos (puede saturar recursos).
- **Lógica de finalización duplicada**: `finalize_and_notify` se llama desde varios lugares con comportamientos ligeramente diferentes.

---

## 2. Data Persistence & Models

- **Sin sistema de migraciones**: Se usa `Base.metadata.create_all()` en `init_db.py`. No hay Alembic.
- **Tabla ExtractedItem infrautilizada**: Existe el modelo pero el flujo principal escribe Parquet shards. El modelo relacional está a medio terminar.
- **Cálculo de progreso y totales fragmentado**: `progress_pct`, `total_rows`, `processed_files` se calculan en `db.py`, `job_manager.py` y `finalize_job_if_complete` de forma inconsistente.
- **Sin versionado de pipeline por documento**: No hay campos como `pipeline_version`, `schema_version` o `extraction_config`.
- **agent_logs como JSON blob limitado**: Se trunca a ~80 eventos, no es indexable ni consultable eficientemente.
- **Falta de transacciones explícitas**: Operaciones como crear job + registrar documentos + escribir storage no están envueltas en transacciones atómicas.
- **Falta de soft deletes y auditoría**: No hay `deleted_at`, `created_by`, `updated_by` de forma consistente.
- **result_manifest_key poco usado**: El campo existe pero la integración con export y UI es parcial.
- **Índices insuficientes documentados**: Solo hay algunos índices básicos; falta estrategia de indexación para consultas de jobs grandes.

---

## 3. Object Storage Abstraction

- **list_prefix en LocalShardedStorage es ineficiente**: Usa `os.walk` completo; puede degradarse con millones de archivos.
- **Sin políticas de retención ni cleanup**: No existe borrado automático de jobs antiguos ni por tamaño/edad.
- **Sin versionado de objetos**: Solo overwrite. No hay soporte para versiones de resultados.
- **MinIO/S3 backend subdesarrollado**: Implementado pero con muy poca cobertura en tests y flujos de jobs reales.
- **Backends limitados**: Solo `local` y `minio`. Faltan S3 nativo (boto3), GCS, Azure Blob, o WebDAV.
- **Falta de soporte avanzado**: No hay multipart uploads, presigned URLs, ni streaming eficiente para archivos muy grandes.
- **get_local_path solo funciona en local**: El resto del código tiene que manejar dos caminos (bytes vs path).
- **Sin métricas de almacenamiento**: No se trackea uso de espacio por job o global.

---

## 4. Document Processing & Agent Orchestration

- **Equipo de 24 agentes es simulado**: Solo genera logs y cambia estados en memoria. No hay ejecución real de agentes ni orquestación distribuida.
- **AgentTeamOrchestrator con lógica legacy dividida**: Mantiene dos caminos (modo pequeño Streamlit + jobs) de forma algo confusa.
- **Manejo de PDFs escaneados/OCR limitado**: La cascada existe pero sigue siendo débil para documentos de baja calidad (según documentación histórica).
- **Sin versionado del extractor**: No se registra qué versión/configuración del pipeline procesó cada documento.
- **Manejo de errores de LLM mejorable**: Rate limits, context overflow, JSON inválido y reintentos no están bien cubiertos en todos los paths.
- **ReconciliationEngine no integrado**: Existe lógica de auditoría de precios pero no está cableado al flujo de jobs ni a la página 10.
- **LiveQARunner vs _light_qa**: Hay dos implementaciones de QA (una completa y una muy básica dentro del JobManager).
- **Sin tracking de costos por documento/job**: No se registran tokens consumidos, llamadas a LLM, ni tiempo de procesamiento.
- **Pipeline no expone métricas internas**: Difícil saber cuántos ítems vinieron de tablas vs LLM vs OCR.

---

## 5. External Integrations (Email + Webhooks)

- **Outlook / Microsoft Graph es stub**: `fetch_outlook_pdfs` solo imprime un mensaje. Requiere Azure AD app + MSAL completo.
- **Webhooks extremadamente básicos**: `send_webhook` hace un `requests.post` fire-and-forget sin reintentos, firma, ni registro de entregas.
- **Sin ingesta programada**: Celery Beat se menciona en specs y `celery_app.py` pero no hay tareas periódicas reales (ej. ingesta automática de email).
- **Gmail sin rate limiting ni manejo de cuotas**: Puede fallar silenciosamente con cuentas grandes.
- **Gestión de credenciales OAuth basada en archivos**: `credentials.json` / `token.json` en raíz del proyecto (problemático en Docker/K8s y multiusuario).
- **EmailSender limitado**: Solo texto plano. Adjuntos y HTML están como "you can extend".
- **Sin soporte para otros proveedores de email**: Solo Gmail (y stub de Outlook).
- **Falta de reintentos y DLQ para webhooks y notificaciones**.

---

## 6. API Layer

- **Mezcla legacy + nuevo sistema**: `sessions_db` en memoria sigue existiendo junto al sistema de jobs. Código duplicado y confuso.
- **Cero autenticación y autorización**: Cualquiera puede crear jobs, listar jobs, o llamar endpoints vía API.
- **Sin rate limiting ni límites de recursos**: Riesgo de abuso y OOM con uploads masivos.
- **Falta de endpoints de control de jobs**: No hay re-procesar documento específico, cancelar job, pausar, o listar documentos fallidos.
- **Webhooks sin confiabilidad**: Se disparan pero no hay cola, reintentos, ni firma de seguridad (HMAC).
- **Health endpoint demasiado básico**: Solo dice "ok" + conteo de agentes.
- **Falta de paginación y filtros avanzados** en listados de jobs.
- **Sin OpenAPI security schemes** documentados.
- **Validación de entrada débil** en uploads grandes.

---

## 7. Streamlit UI & User Experience

- **Dos mundos paralelos**: Páginas legacy (1-9) vs página 10 de jobs. Navegación, estado y flujo no están unificados.
- **Todo basado en polling**: Monitoreo de jobs requiere botones de "Refrescar". No hay actualizaciones en tiempo real (SSE, WebSockets, ni st.fragment con auto-rerun).
- **Falta de revisión humana integrada**: Las páginas antiguas de revisión, comparación y mapeo no están conectadas al sistema de jobs.
- **UI de jobs incompleta**:
  - No hay vista clara de documentos fallidos por job.
  - No hay detalle de shards individuales ni preview de resultados consolidados.
  - Falta "cola de workers" y estado de workers.
- **Inconsistencias en títulos y numeración**: Todavía quedan referencias a "8. Exportación" o números de página antiguos en algunos lugares.
- **Estado de Streamlit frágil**: `st.session_state` se comparte entre modo legacy y jobs de forma riesgosa.
- **Sin Human-in-the-Loop real** dentro del flujo escalable.
- **Falta de acciones por job**: Botones como "Re-procesar fallidos", "Cancelar", "Cambiar llm_mode después de creado", etc.

---

## 8. Configuration, Secrets & Environment

- **Uso masivo de `os.getenv` disperso**: Sin capa centralizada de configuración.
- **Sin pydantic-settings ni validación**: No hay modelo de Settings con validación de tipos y valores por defecto.
- **Manejo de secrets frágil**: Credenciales Gmail, tokens y API keys viven en archivos locales o `.env`.
- **Doble configuración LLM**: `llm_mode` por job + variables de entorno globales (`AUDITOR_LLM_MODE`) generan confusión.
- **Archivos de credenciales esperados en raíz**: `credentials.json`, `token.json` hardcodeados en varios módulos.
- **Falta de perfiles de entorno** (dev / staging / prod) con configuraciones distintas.
- **Variables de storage y DB no siempre consistentes** entre componentes.

---

## 9. Deployment, Infrastructure & Operations

- **No existe Dockerfile de la aplicación**: Solo hay `docker-compose.yml` para infraestructura (Redis + MinIO).
- **docker-compose.yml incompleto**:
  - No levanta la aplicación Streamlit ni la API.
  - Configuración de volúmenes y servicios está parcialmente comentada.
  - Falta definición de la app + workers.
- **Sin estrategia de orquestación de workers**: No hay scripts fáciles para lanzar N workers simples o workers Celery con concurrencia.
- **Falta de health/readiness probes avanzados**: Solo endpoint básico.
- **Sin backups ni estrategia de recuperación**: Ni para la base de datos ni para el storage.
- **init_db.py es manual**: No se ejecuta automáticamente de forma robusta en todos los entrypoints (API, workers, UI).
- **Sin logging centralizado ni agregación**.
- **Sin soporte para zero-downtime o rolling updates**.
- **Falta de Flower u otro dashboard** cuando se usa Celery.

---

## 10. Security & Access Control

- **Ausencia total de autenticación**: Ni en API ni en el sistema de jobs.
- **Sin ownership de jobs**: Cualquiera puede ver y operar sobre cualquier job.
- **Sin aislamiento multi-tenant**: No hay concepto de organización, usuario o proyecto.
- **Secrets en texto plano** en el árbol del proyecto o en variables de entorno sin cifrado.
- **Sin logging de acciones sensibles**: No se registra quién creó un job, exportó resultados, etc.
- **Riesgo de path traversal** mitigado solo parcialmente en `LocalShardedStorage`.
- **Sin consideraciones de retención de datos** ni borrado selectivo (cumplimiento normativo).
- **Webhooks sin firma**: Cualquiera puede suplantar el origen si se intercepta la URL.

---

## 11. Observability, Logging & Monitoring

- **Sin logging estructurado**: Se usa `logging` estándar sin contexto, correlation IDs ni campos consistentes.
- **Sin métricas**: No hay contadores de jobs procesados, filas extraídas, errores por tipo, latencia, etc.
- **Sin tracing / correlation ID**: Imposible seguir un job a través de UI → API → worker → storage → email.
- **agent_logs muy limitados**: Solo últimos 80 eventos en JSON. No hay consulta histórica ni agregaciones.
- **Sin visibilidad de uso de recursos**: CPU, memoria, tokens LLM, espacio en storage por job.
- **Sin alertas**: No hay forma de notificar cuando un worker cae, un job se atasca, o se detectan muchos fallos.
- **Sin dashboard operativo** (ni siquiera uno básico con Streamlit o externo).

---

## 12. Testing & Quality Assurance

- **Baja cobertura en el sistema nuevo**:
  - JobManager, workers, email_ingest, storage backends, export, finalize logic.
  - Endpoints de jobs en la API.
- **Sin tests de ciclo completo de job**: Crear job → worker procesa → export → notificación.
- **Sin tests de concurrencia**: Race conditions entre workers, reintentos, etc.
- **Sin tests de integración con storage real** (MinIO).
- **Sin tests de performance / carga**.
- **Muchos tests legacy saltan LLM** (`use_llm=False`) y no cubren paths reales de fallback.
- **Falta de tests de contratos** entre JobManager, Storage y DB.

---

## 13. Business Logic: Reconciliation & Auditing

- **ReconciliationEngine no integrado** en el flujo de jobs (sigue siendo código legacy).
- **No hay reconciliación automática** al finalizar un job grande.
- **Falta de hallazgos persistidos** por job o por ítem (actualmente solo se generan en memoria en el motor antiguo).
- **Sin UI para revisar hallazgos** de auditoría a escala.
- **ProviderIdentifier** existe pero su uso es limitado fuera del motor antiguo.
- **No hay reglas de negocio versionadas** ni configuración de umbrales de discrepancia por proveedor o categoría.

---

## 14. Scalability, Performance & Resilience

- **Streamlit single-process**: Cuello de botella para usuarios concurrentes cuando hay jobs grandes corriendo.
- **Consolidación de export en memoria**: `pd.concat` de todos los shards puede causar OOM con jobs de cientos de miles de filas.
- **Sin backpressure**: Cualquier cantidad de jobs puede entrar a "processing".
- **Sin caché** (Redis solo se usa para Celery broker/backend).
- **Pipeline sin circuit breaker** claro para fallos de LLM o APIs externas.
- **Sin estimación previa de costo/tiempo** antes de crear jobs masivos.
- **Lectura de shards uno por uno** en export sin paralelismo ni chunking.
- **Falta de particionado / sharding** a nivel de storage para jobs extremadamente grandes.

---

## 15. Documentation, Maintainability & Developer Experience

- **Specs parcialmente desactualizados**: `scaling_plan_v1.md`, `system_architecture.md` y `workflow_rules.md` no reflejan exactamente el estado actual (números de página, módulos nuevos, etc.).
- **Archivo histórico** `docs/documentacion para terminar app.txt` ya no representa la arquitectura actual.
- **Sin Architecture Decision Records (ADRs)**: Decisiones importantes (Parquet shards, dos tipos de workers, llm_mode, etc.) no están documentadas formalmente.
- **Mezcla de español e inglés**: En nombres de variables, comentarios, mensajes de UI y logs.
- **Falta de runbooks operativos**: Cómo recuperar un job atascado, cómo hacer cleanup de storage, cómo rotar credenciales Gmail, etc.
- **README bueno pero insuficiente** para operación a escala.
- **Código legacy mezclado**: Archivos como `session_manager.py`, partes de `document_parser.py` y páginas antiguas generan confusión sobre qué camino es el "oficial".
- **Sin CONTRIBUTING ni guía de desarrollo** clara.
- **Muchos warnings de CRLF** por desarrollo en Windows (LF/CRLF inconsistente).

---

## Notas Adicionales Generales

- `venv/` aparece en el árbol (debería estar en `.gitignore`).
- Hay datos de prueba en `outputs/`, `storage/`, `temp_pdf_viewer/`.
- El proyecto tiene una buena base de tests en las partes antiguas de extracción, pero el sistema de jobs está sub-testado.
- La decisión de ir a Parquet + workers + storage abstraction es sólida; los gaps están principalmente en **operabilidad, resiliencia, seguridad y completitud del dominio de negocio**.

---

**Próximos pasos sugeridos (si se desea):**
- Convertir este backlog en issues de GitHub.
- Crear un plan por oleadas (Wave 1: Observabilidad + Workers robustos, Wave 2: Seguridad + Auth, etc.).
- Generar ADRs para las decisiones clave que se tomen al cerrar estos gaps.

---
*Generado a partir de revisión exhaustiva del código actual (core/, workers/, api/, ui/pages/, storage, db, email, specs, etc.).*
