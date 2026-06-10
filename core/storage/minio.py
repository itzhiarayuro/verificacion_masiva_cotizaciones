from __future__ import annotations
import os
from io import BytesIO
from pathlib import Path
from typing import BinaryIO, Iterator

try:
    from minio import Minio
    from minio.error import S3Error
    MINIO_AVAILABLE = True
except Exception:
    MINIO_AVAILABLE = False

from .base import StorageBackend, StorageObject


class MinioStorage(StorageBackend):
    """MinIO / S3-compatible backend. Requires 'minio' package."""

    def __init__(self):
        if not MINIO_AVAILABLE:
            raise RuntimeError("minio package not installed. pip install minio")
        endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        self.bucket = os.getenv("MINIO_BUCKET", "auditor-cotizaciones")

        self.client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)

        # Ensure bucket exists
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def _put(self, key: str, data: bytes | BinaryIO, size: int | None, content_type: str | None):
        self.client.put_object(
            self.bucket,
            key,
            data if not isinstance(data, (bytes, bytearray)) else BytesIO(data),
            length=size or -1,
            content_type=content_type or "application/octet-stream",
        )
        return StorageObject(key=key, size=size, content_type=content_type)

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> StorageObject:
        return self._put(key, data, len(data), content_type)

    def put_file(self, key: str, src_path: str | Path, content_type: str | None = None) -> StorageObject:
        size = Path(src_path).stat().st_size
        with open(src_path, "rb") as f:
            return self._put(key, f, size, content_type)

    def get_bytes(self, key: str) -> bytes:
        response = self.client.get_object(self.bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def get_stream(self, key: str) -> BinaryIO:
        # Return the raw response; caller responsible for close
        return self.client.get_object(self.bucket, key)

    def exists(self, key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise

    def delete(self, key: str) -> None:
        try:
            self.client.remove_object(self.bucket, key)
        except S3Error:
            pass

    def list_prefix(self, prefix: str) -> Iterator[StorageObject]:
        objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=True)
        for obj in objects:
            yield StorageObject(key=obj.object_name, size=obj.size, content_type=obj.content_type)
