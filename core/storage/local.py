from __future__ import annotations
import os
import shutil
from pathlib import Path
from typing import BinaryIO, Iterator, Optional

from .base import StorageBackend, StorageObject


class LocalShardedStorage(StorageBackend):
    """
    Local filesystem "object storage" with simple sharding.
    Base dir: configurable via AUDITOR_STORAGE_DIR (default: ./storage)
    Keys are treated as relative paths.
    Good for dev, single server, or as fallback.
    """

    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or os.getenv("AUDITOR_STORAGE_DIR", "storage")).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _full_path(self, key: str) -> Path:
        # Prevent path traversal
        safe_key = key.lstrip("/\\")
        p = (self.base_dir / safe_key).resolve()
        if not str(p).startswith(str(self.base_dir)):
            raise ValueError("Invalid storage key (path traversal)")
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> StorageObject:
        path = self._full_path(key)
        path.write_bytes(data)
        return StorageObject(key=key, size=len(data), content_type=content_type)

    def put_file(self, key: str, src_path: str | Path, content_type: str | None = None) -> StorageObject:
        src = Path(src_path)
        dst = self._full_path(key)
        shutil.copy2(src, dst)
        size = dst.stat().st_size
        return StorageObject(key=key, size=size, content_type=content_type)

    def get_bytes(self, key: str) -> bytes:
        return self._full_path(key).read_bytes()

    def get_stream(self, key: str) -> BinaryIO:
        return open(self._full_path(key), "rb")

    def exists(self, key: str) -> bool:
        return self._full_path(key).exists()

    def delete(self, key: str) -> None:
        p = self._full_path(key)
        if p.exists():
            if p.is_file():
                p.unlink()
            else:
                shutil.rmtree(p)

    def list_prefix(self, prefix: str) -> Iterator[StorageObject]:
        root = self._full_path(prefix)
        if not root.exists():
            return
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                full = Path(dirpath) / fn
                rel = full.relative_to(self.base_dir)
                yield StorageObject(key=str(rel).replace("\\", "/"), size=full.stat().st_size)

    def get_local_path(self, key: str) -> Optional[str]:
        p = self._full_path(key)
        return str(p) if p.exists() else None
