from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def checksum_for_file(path: str | Path) -> str | None:
    file_path = Path(path)
    if not file_path.is_file():
        return None
    digest = sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def size_bytes_for_file(path: str | Path) -> int | None:
    file_path = Path(path)
    if not file_path.exists():
        return None
    return file_path.stat().st_size


def stable_asset_id(project_id: str, asset_type: str, run_id: str, *, language: str | None = None) -> str:
    digest = sha256(f"{project_id}:{asset_type}:{language or ''}:{run_id}".encode("utf-8")).hexdigest()
    return f"asset_{digest[:16]}"


@dataclass(frozen=True)
class MediaAsset:
    asset_id: str
    project_id: str
    type: str
    language: str | None
    uri: str
    format: str
    duration_ms: int | None
    size_bytes: int | None
    checksum: str | None = None
    created_at: str = field(default_factory=utc_timestamp)
    storage_key: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "asset_id": self.asset_id,
            "project_id": self.project_id,
            "type": self.type,
            "language": self.language,
            "uri": self.uri,
            "format": self.format,
            "duration_ms": self.duration_ms,
            "size_bytes": self.size_bytes,
            "created_at": self.created_at,
        }
        if self.checksum:
            payload["checksum"] = self.checksum
        if self.storage_key:
            payload["storage_key"] = self.storage_key
        return payload
