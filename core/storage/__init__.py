"""Object storage abstraction for original PDFs and result artifacts (Parquet, logs, etc.).

Local sharded implementation is default (zero extra services).
MinIO / S3-compatible ready.
"""

from .base import StorageBackend, StorageObject
from .local import LocalShardedStorage

__all__ = ["StorageBackend", "StorageObject", "LocalShardedStorage", "get_storage"]

def get_storage(backend: str | None = None) -> StorageBackend:
    """Factory. backend='local' (default) or 'minio'."""
    backend = (backend or "local").lower()
    if backend in ("local", "filesystem", "fs"):
        return LocalShardedStorage()
    if backend in ("minio", "s3"):
        from .minio import MinioStorage
        return MinioStorage()
    raise ValueError(f"Unknown storage backend: {backend}")
