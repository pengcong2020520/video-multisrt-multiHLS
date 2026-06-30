from __future__ import annotations

import hmac
import time
from hashlib import sha256
from typing import Protocol
from urllib.parse import quote

from app.domain.file_paths import storage_key_from_private_uri


class ObjectStoragePort(Protocol):
    def generate_upload_url(self, storage_key: str) -> str:
        ...

    def generate_download_url(self, private_uri: str) -> str:
        ...


class SignedUrlObjectStorage:
    def __init__(self, public_url_base: str, secret: str, ttl_seconds: int = 3600) -> None:
        self.public_url_base = public_url_base.rstrip("/")
        self.secret = secret.encode("utf-8")
        self.ttl_seconds = ttl_seconds

    def generate_upload_url(self, storage_key: str) -> str:
        return self._signed_url("upload", storage_key)

    def generate_download_url(self, private_uri: str) -> str:
        return self._signed_url("download", storage_key_from_private_uri(private_uri))

    def _signed_url(self, action: str, storage_key: str) -> str:
        expires = int(time.time()) + self.ttl_seconds
        payload = f"{action}:{storage_key}:{expires}".encode("utf-8")
        signature = hmac.new(self.secret, payload, sha256).hexdigest()
        encoded_key = quote(storage_key, safe="")
        return (
            f"{self.public_url_base}/{action}/{encoded_key}"
            f"?expires={expires}&signature={signature}"
        )
