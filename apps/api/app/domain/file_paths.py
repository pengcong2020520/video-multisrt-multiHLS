from __future__ import annotations

from app.domain.enums import AssetType

PRIVATE_URI_PREFIX = "storage://private/"


def storage_key_for_asset(
    project_id: str,
    asset_type: AssetType | str,
    *,
    language: str | None = None,
    segment_id: str | None = None,
    version_id: str | None = None,
) -> str:
    asset_type = AssetType(asset_type)
    match asset_type:
        case AssetType.SOURCE_VIDEO:
            return f"projects/{project_id}/source/source.mp4"
        case AssetType.SOURCE_AUDIO:
            return f"projects/{project_id}/source/source.wav"
        case AssetType.SOURCE_VOCAL:
            return f"projects/{project_id}/separation/vocals.wav"
        case AssetType.BACKGROUND_AUDIO:
            return f"projects/{project_id}/separation/background.wav"
        case AssetType.SUBTITLE_SRT:
            return f"projects/{project_id}/subtitles/{_require_language(language)}.srt"
        case AssetType.SUBTITLE_VTT:
            return f"projects/{project_id}/subtitles/{_require_language(language)}.vtt"
        case AssetType.TTS_SEGMENT_AUDIO:
            return (
                f"projects/{project_id}/tts/{_require_language(language)}/"
                f"{_require_segment_id(segment_id)}.wav"
            )
        case AssetType.TARGET_VOCAL:
            return f"projects/{project_id}/audio/{_require_language(language)}.vocal.wav"
        case AssetType.TARGET_MIX_AUDIO:
            return f"projects/{project_id}/audio/{_require_language(language)}.mix.m4a"
        case AssetType.PREVIEW_VIDEO:
            return f"projects/{project_id}/preview/{_require_language(language)}.mp4"
        case AssetType.PACKAGE_ZIP:
            return f"projects/{project_id}/packages/{version_id or 'latest'}.zip"
        case _:
            raise ValueError(f"unsupported asset type: {asset_type}")


def private_uri(storage_key: str) -> str:
    return f"{PRIVATE_URI_PREFIX}{storage_key}"


def storage_key_from_private_uri(uri: str) -> str:
    if not uri.startswith(PRIVATE_URI_PREFIX):
        raise ValueError("asset uri is not a private storage uri")
    return uri[len(PRIVATE_URI_PREFIX) :]


def _require_language(language: str | None) -> str:
    if not language:
        raise ValueError("language is required for this asset type")
    return language


def _require_segment_id(segment_id: str | None) -> str:
    if not segment_id:
        raise ValueError("segment_id is required for this asset type")
    return segment_id
