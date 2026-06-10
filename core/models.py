from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import String, Integer, Float, DateTime, JSON, ForeignKey, Text, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # uuid
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending, processing, completed, failed, partial
    source_type: Mapped[str] = mapped_column(String(20), default="upload")  # upload, email, api, folder
    source_meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=None)  # e.g. {"email_query": "...", "account": "..."}

    total_files: Mapped[int] = mapped_column(Integer, default=0)
    processed_files: Mapped[int] = mapped_column(Integer, default=0)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)

    llm_mode: Mapped[str] = mapped_column(String(20), default="fallback")  # none | fallback | always
    batch_size: Mapped[int] = mapped_column(Integer, default=50)

    storage_prefix: Mapped[Optional[str]] = mapped_column(String(200), default=None)
    result_manifest_key: Mapped[Optional[str]] = mapped_column(String(300), default=None)  # e.g. jobs/xxx/results/manifest.json or .parquet list

    webhook_url: Mapped[Optional[str]] = mapped_column(String(500), default=None)
    notify_email: Mapped[Optional[str]] = mapped_column(String(200), default=None)

    error: Mapped[Optional[str]] = mapped_column(Text, default=None)
    progress_pct: Mapped[float] = mapped_column(Float, default=0.0)

    # Convenience for UI
    agent_logs: Mapped[Optional[list]] = mapped_column(JSON, default=list)  # last N agent-style events

    # Export tracking for massive consolidated results (Phase 2 error handling)
    export_status: Mapped[str] = mapped_column(String(20), default="")  # success, partial, failed, ""
    export_errors: Mapped[Optional[list]] = mapped_column(JSON, default=list)  # list of {"shard": , "error": }
    export_row_count: Mapped[int] = mapped_column(Integer, default=0)
    export_manifest_key: Mapped[Optional[str]] = mapped_column(String(300), default=None)  # points to detailed .json manifest

    documents: Mapped[list["Document"]] = relationship("Document", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_jobs_status_created", "status", "created_at"),
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(300))
    storage_key: Mapped[str] = mapped_column(String(400))  # original PDF location in storage

    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending, processing, completed, failed
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    extraction_method: Mapped[Optional[str]] = mapped_column(String(50), default=None)  # markitdown, pdfplumber, ocr, llm, mixed

    qa_passed: Mapped[int] = mapped_column(Integer, default=0)
    qa_rate: Mapped[float] = mapped_column(Float, default=0.0)
    preview_json: Mapped[Optional[list[dict]]] = mapped_column(JSON, default=None)  # small sample rows for live view

    error: Mapped[Optional[str]] = mapped_column(Text, default=None)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=None)

    job: Mapped["Job"] = relationship("Job", back_populates="documents")

    __table_args__ = (
        Index("ix_documents_job_status", "job_id", "status"),
    )


# Optional: if you want fully relational line items for small/medium jobs
# (For 1M+ we recommend Parquet shards in storage instead.)
class ExtractedItem(Base):
    __tablename__ = "extracted_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(36), index=True)
    document_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), index=True)
    filename: Mapped[str] = mapped_column(String(300))

    # Core columns (match CSV_COLUMNS + extras)
    cod_item: Mapped[Optional[str]] = mapped_column(String(50))
    cod_cotizacion: Mapped[Optional[str]] = mapped_column(String(50))
    proveedor: Mapped[Optional[str]] = mapped_column(String(200))
    descripcion: Mapped[str] = mapped_column(Text)
    cantidad: Mapped[Optional[str]] = mapped_column(String(50))
    precio_unitario: Mapped[Optional[str]] = mapped_column(String(100))
    precio_total: Mapped[Optional[str]] = mapped_column(String(100))
    nit: Mapped[Optional[str]] = mapped_column(String(100))
    moneda: Mapped[Optional[str]] = mapped_column(String(10), default="COP")
    tiempo_entrega: Mapped[Optional[str]] = mapped_column(String(100))
    forma_pago: Mapped[Optional[str]] = mapped_column(String(100))
    vigencia: Mapped[Optional[str]] = mapped_column(String(100))
    comercial: Mapped[Optional[str]] = mapped_column(String(150))
    correo: Mapped[Optional[str]] = mapped_column(String(150))
    telefono: Mapped[Optional[str]] = mapped_column(String(100))
    pagina: Mapped[Optional[int]] = mapped_column(Integer)
    confianza: Mapped[Optional[str]] = mapped_column(String(20))
    fuente: Mapped[Optional[str]] = mapped_column(String(30))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
