from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import BinaryIO, Iterator, Optional
from pathlib import Path


@dataclass
class StorageObject:
    key: str
    size: int | None = None
    content_type: str | None = None


class StorageBackend(ABC):
    """Minimal object storage interface used by the job system."""

    @abstractmethod
    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> StorageObject:
        """Store bytes under key (e.g. 'jobs/abc123/originals/file.pdf')."""
        ...

    @abstractmethod
    def put_file(self, key: str, src_path: str | Path, content_type: str | None = None) -> StorageObject:
        """Store from local path (more efficient for large files)."""
        ...

    @abstractmethod
    def get_bytes(self, key: str) -> bytes:
        """Return full content. Use only for small/medium files or when necessary."""
        ...

    @abstractmethod
    def get_stream(self, key: str) -> BinaryIO:
        """Return a file-like stream (caller must close)."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        ...

    @abstractmethod
    def list_prefix(self, prefix: str) -> Iterator[StorageObject]:
        """List objects under prefix."""
        ...

    def get_local_path(self, key: str) -> Optional[str]:
        """If backend supports direct filesystem access (LocalShardedStorage), return path.
        Otherwise return None (caller should use get_stream/get_bytes).
        """
        return None
