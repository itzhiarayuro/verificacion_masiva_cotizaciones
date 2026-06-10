"""
Módulo central de observabilidad para el sistema de Jobs.

Proporciona:
- Correlation ID (usando job_id como identificador principal)
- Helpers para logging con contexto
- Futura integración con métricas y tracing

Uso típico:
    from core.observability import set_correlation_id, get_correlation_id, get_logger

    set_correlation_id(job.id)
    logger = get_logger(__name__)
    logger.info("Procesando documento", extra={"document": filename})
"""

from __future__ import annotations

import contextvars
import logging
from typing import Optional, Any, Dict

# Context variable para correlation_id (thread-safe y task-safe en async)
_correlation_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)


def set_correlation_id(job_id: str) -> None:
    """Establece el correlation ID actual (normalmente el job.id)."""
    _correlation_id.set(job_id)


def get_correlation_id() -> Optional[str]:
    """Obtiene el correlation ID actual."""
    return _correlation_id.get()


def clear_correlation_id() -> None:
    """Limpia el correlation ID (útil en tests o al final de un contexto)."""
    _correlation_id.set(None)


class ContextLogger:
    """
    Wrapper simple sobre logging.Logger que inyecta correlation_id automáticamente.
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _get_extra(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        base: Dict[str, Any] = {}
        cid = get_correlation_id()
        if cid:
            base["correlation_id"] = cid
        if extra:
            base.update(extra)
        return base

    def debug(self, msg: str, *args: Any, extra: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        self._logger.debug(msg, *args, extra=self._get_extra(extra), **kwargs)

    def info(self, msg: str, *args: Any, extra: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        self._logger.info(msg, *args, extra=self._get_extra(extra), **kwargs)

    def warning(self, msg: str, *args: Any, extra: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        self._logger.warning(msg, *args, extra=self._get_extra(extra), **kwargs)

    def error(self, msg: str, *args: Any, extra: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        self._logger.error(msg, *args, extra=self._get_extra(extra), **kwargs)

    def exception(self, msg: str, *args: Any, extra: Optional[Dict[str, Any]] = None, **kwargs: Any) -> None:
        self._logger.exception(msg, *args, extra=self._get_extra(extra), **kwargs)


def get_logger(name: str) -> ContextLogger:
    """
    Retorna un logger con soporte de correlation_id.
    Uso recomendado en lugar de logging.getLogger(__name__).
    """
    return ContextLogger(name)


# Atajo para compatibilidad
get_context_logger = get_logger
