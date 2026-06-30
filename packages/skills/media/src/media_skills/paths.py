from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse


PRIVATE_URI_PREFIX = "storage://private/"


class AssetType:
    SOURCE_VIDEO = "source_video"
    SOURCE_AUDIO = "source_audio"
    SOURCE_VOCAL = "source_vocal"
    BACKGROUND_AUDIO = "background_audio"


def source_path(project_id: str, fmt: str) -> str:
    return f"projects/{project_id}/source/source.{fmt}"


def separation_path(project_id: str, kind: str) -> str:
    if kind not in {"vocals", "background"}:
        raise ValueError("separation kind must be vocals or background")
    return f"projects/{project_id}/separation/{kind}.wav"


def storage_key_for_asset(project_id: str, asset_type: str) -> str:
    match asset_type:
        case AssetType.SOURCE_VIDEO:
            return source_path(project_id, "mp4")
        case AssetType.SOURCE_AUDIO:
            return source_path(project_id, "wav")
        case AssetType.SOURCE_VOCAL:
            return separation_path(project_id, "vocals")
        case AssetType.BACKGROUND_AUDIO:
            return separation_path(project_id, "background")
        case _:
            raise ValueError(f"unsupported media asset type: {asset_type}")


def private_uri(storage_key: str) -> str:
    return f"{PRIVATE_URI_PREFIX}{storage_key}"


def storage_key_from_private_uri(uri: str) -> str:
    if not uri.startswith(PRIVATE_URI_PREFIX):
        raise ValueError("asset uri is not a private storage uri")
    return uri[len(PRIVATE_URI_PREFIX) :]


@dataclass(frozen=True)
class OutputLocation:
    storage_key: str
    uri: str
    local_path: Path


class StoragePathResolver:
    def __init__(self, storage_root: str | Path | None = None) -> None:
        self.storage_root = Path(storage_root) if storage_root else None

    def input_path(self, asset: dict[str, object]) -> str:
        uri = str(asset.get("uri") or "")
        if not uri:
            raise ValueError("asset uri is required")
        if uri.startswith(PRIVATE_URI_PREFIX):
            key = storage_key_from_private_uri(uri)
            return str((self.storage_root / key) if self.storage_root else Path(key))
        parsed = urlparse(uri)
        if parsed.scheme == "file":
            return str(Path(unquote(parsed.path)))
        if parsed.scheme:
            return uri
        return str(Path(uri))

    def output_location(self, project_id: str, asset_type: str) -> OutputLocation:
        storage_key = storage_key_for_asset(project_id, asset_type)
        local_path = (self.storage_root / storage_key) if self.storage_root else Path(storage_key)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        return OutputLocation(
            storage_key=storage_key,
            uri=private_uri(storage_key),
            local_path=local_path,
        )
