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
    SUBTITLE_SRT = "subtitle_srt"
    SUBTITLE_VTT = "subtitle_vtt"
    TTS_SEGMENT_AUDIO = "tts_segment_audio"
    TARGET_VOCAL = "target_vocal"
    TARGET_MIX_AUDIO = "target_mix_audio"
    PREVIEW_VIDEO = "preview_video"
    PACKAGE_ZIP = "package_zip"


def source_path(project_id: str, fmt: str) -> str:
    return f"projects/{project_id}/source/source.{fmt}"


def separation_path(project_id: str, kind: str) -> str:
    if kind not in {"vocals", "background"}:
        raise ValueError("separation kind must be vocals or background")
    return f"projects/{project_id}/separation/{kind}.wav"


def subtitle_path(project_id: str, language: str, fmt: str) -> str:
    if fmt not in {"srt", "vtt"}:
        raise ValueError("subtitle format must be srt or vtt")
    return f"projects/{project_id}/subtitles/{language}.{fmt}"


def tts_segment_path(project_id: str, language: str, segment_id: str) -> str:
    return f"projects/{project_id}/tts/{language}/{segment_id}.wav"


def audio_path(project_id: str, language: str, kind: str) -> str:
    if kind == "vocal":
        return f"projects/{project_id}/audio/{language}.vocal.wav"
    if kind == "mix":
        return f"projects/{project_id}/audio/{language}.mix.m4a"
    raise ValueError("audio kind must be vocal or mix")


def preview_path(project_id: str, language: str) -> str:
    return f"projects/{project_id}/preview/{language}.mp4"


def package_path(project_id: str, version_id: str) -> str:
    return f"projects/{project_id}/packages/{version_id}.zip"


def storage_key_for_asset(
    project_id: str,
    asset_type: str,
    *,
    language: str | None = None,
    version_id: str | None = None,
    segment_id: str | None = None,
    source_format: str = "mp4",
) -> str:
    match asset_type:
        case AssetType.SOURCE_VIDEO:
            return source_path(project_id, source_format)
        case AssetType.SOURCE_AUDIO:
            return source_path(project_id, "wav")
        case AssetType.SOURCE_VOCAL:
            return separation_path(project_id, "vocals")
        case AssetType.BACKGROUND_AUDIO:
            return separation_path(project_id, "background")
        case AssetType.SUBTITLE_SRT:
            return subtitle_path(project_id, _required(language, "language"), "srt")
        case AssetType.SUBTITLE_VTT:
            return subtitle_path(project_id, _required(language, "language"), "vtt")
        case AssetType.TTS_SEGMENT_AUDIO:
            return tts_segment_path(project_id, _required(language, "language"), _required(segment_id, "segment_id"))
        case AssetType.TARGET_VOCAL:
            return audio_path(project_id, _required(language, "language"), "vocal")
        case AssetType.TARGET_MIX_AUDIO:
            return audio_path(project_id, _required(language, "language"), "mix")
        case AssetType.PREVIEW_VIDEO:
            return preview_path(project_id, _required(language, "language"))
        case AssetType.PACKAGE_ZIP:
            return package_path(project_id, _required(version_id, "version_id"))
        case _:
            raise ValueError(f"unsupported packaging asset type: {asset_type}")


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
        path = asset.get("path") or asset.get("local_path")
        if path:
            return str(path)
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

    def output_location(
        self,
        project_id: str,
        asset_type: str,
        *,
        language: str | None = None,
        version_id: str | None = None,
        segment_id: str | None = None,
        source_format: str = "mp4",
    ) -> OutputLocation:
        storage_key = storage_key_for_asset(
            project_id,
            asset_type,
            language=language,
            version_id=version_id,
            segment_id=segment_id,
            source_format=source_format,
        )
        local_path = (self.storage_root / storage_key) if self.storage_root else Path(storage_key)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        return OutputLocation(storage_key=storage_key, uri=private_uri(storage_key), local_path=local_path)


def _required(value: str | None, name: str) -> str:
    if not value:
        raise ValueError(f"{name} is required")
    return value
