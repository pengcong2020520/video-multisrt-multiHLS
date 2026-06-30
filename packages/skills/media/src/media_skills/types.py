from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any


QualityFlag = dict[str, Any]


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


def stable_asset_id(project_id: str, asset_type: str, run_id: str) -> str:
    digest = sha256(f"{project_id}:{asset_type}:{run_id}".encode("utf-8")).hexdigest()
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
        return payload


@dataclass(frozen=True)
class AudioStreamMetadata:
    codec: str | None
    sample_rate: int | None
    channels: int | None
    channel_layout: str | None
    bit_rate: int | None
    duration_ms: int | None
    language: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "codec": self.codec,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "channel_layout": self.channel_layout,
            "bit_rate": self.bit_rate,
            "duration_ms": self.duration_ms,
            "language": self.language,
        }


@dataclass(frozen=True)
class ProbeMetadata:
    duration_ms: int
    format: str
    codec: str | None
    has_audio: bool
    audio_stream: AudioStreamMetadata | None
    video_codec: str | None
    audio_codec: str | None
    width: int | None
    height: int | None
    fps: float | None
    size_bytes: int | None
    quality_flags: list[QualityFlag] = field(default_factory=list)

    def to_skill_output(self) -> dict[str, Any]:
        return {
            "duration_ms": self.duration_ms,
            "format": self.format,
            "container": self.format,
            "codec": self.codec,
            "has_audio": self.has_audio,
            "audio_stream": self.audio_stream.to_dict() if self.audio_stream else None,
            "video_codec": self.video_codec,
            "audio_codec": self.audio_codec,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "size_bytes": self.size_bytes,
            "quality_flags": self.quality_flags,
        }


@dataclass(frozen=True)
class SeparationResult:
    quality_score: float | None
    quality_flags: list[QualityFlag] = field(default_factory=list)
