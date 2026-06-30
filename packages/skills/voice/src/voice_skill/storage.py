from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

from voice_skill.paths import private_uri


class AudioAssetWriter:
    def __init__(self, *, storage_root: str | Path | None = None) -> None:
        self.storage_root = Path(storage_root) if storage_root else None

    def write_audio(
        self,
        storage_key: str,
        audio: bytes,
        *,
        project_id: str,
        language: str,
        duration_ms: int | None,
    ) -> dict[str, Any]:
        if self.storage_root is not None:
            destination = self.storage_root / storage_key
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(audio)

        return {
            "asset_id": _asset_id_from_key(storage_key),
            "project_id": project_id,
            "type": "tts_segment_audio",
            "language": language,
            "uri": private_uri(storage_key),
            "storage_key": storage_key,
            "format": "wav",
            "duration_ms": duration_ms,
            "size_bytes": len(audio),
            "checksum": f"sha256:{sha256(audio).hexdigest()}",
            "created_at": _utc_timestamp(),
        }


def _asset_id_from_key(storage_key: str) -> str:
    safe = storage_key.replace("/", "_").replace(".", "_").replace("-", "_")
    return f"asset_{safe}"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
