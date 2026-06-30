from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import quote, urlparse

from .errors import ErrorCode, PackagingSkillError
from .paths import AssetType, package_path, storage_key_from_private_uri


LANGUAGE_LABELS = {
    "source": "原音轨",
    "zh-CN": "中文",
    "en-US": "English",
    "es-ES": "Español",
    "es-MX": "Español (MX)",
    "pt-BR": "Português (BR)",
}


def build_manifest(
    project_id: str,
    version_id: str,
    payload: Mapping[str, Any],
    *,
    config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    config = config or {}
    assets = collect_assets(payload)
    video_asset = _first_payload_asset(payload, "video", "source_video", "source_video_asset") or _first_by_type(
        assets,
        AssetType.SOURCE_VIDEO,
    )
    if not video_asset:
        raise PackagingSkillError(ErrorCode.PACKAGE_FAILED, "source_video is required to build manifest")

    subtitles = _subtitle_entries(project_id, payload, assets, config)
    audio_tracks = _audio_track_entries(project_id, payload, assets, config)
    downloads = _download_entries(project_id, version_id, payload, assets, config)

    return {
        "project_id": project_id,
        "version_id": version_id,
        "video": {
            "url": public_url_for_asset(video_asset, project_id=project_id, config=config),
            "duration_ms": _int_or_none(video_asset.get("duration_ms") or payload.get("duration_ms")),
        },
        "subtitles": subtitles,
        "audio_tracks": audio_tracks,
        "downloads": downloads,
    }


def collect_assets(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    raw_assets = payload.get("assets")
    if isinstance(raw_assets, list):
        assets.extend(_dict_items(raw_assets))
    elif isinstance(raw_assets, Mapping):
        assets.extend(_dict_items(raw_assets.values()))

    for key in (
        "source_video",
        "source_video_asset",
        "source_audio",
        "source_audio_asset",
        "source_vocal",
        "background_audio",
        "target_vocal",
        "target_mix_audio",
        "package_zip",
    ):
        value = payload.get(key)
        if isinstance(value, Mapping):
            assets.append(dict(value))

    for key in (
        "subtitles",
        "subtitle_assets",
        "audio_tracks",
        "target_mix_audios",
        "target_vocals",
        "tts_segment_audio",
        "tts_segment_audios",
        "tts_assets",
        "downloads",
        "package_assets",
    ):
        value = payload.get(key)
        if isinstance(value, list):
            assets.extend(_dict_items(value))
        elif isinstance(value, Mapping):
            assets.extend(_dict_items(value.values()))

    return _dedupe_assets(assets)


def public_url_for_asset(asset: Mapping[str, Any], *, project_id: str, config: Mapping[str, Any]) -> str:
    for key in ("public_url", "download_url", "url"):
        value = asset.get(key)
        if _is_public_url(value):
            return str(value)

    storage_key = _storage_key_for_public_url(asset)
    if storage_key:
        return public_url_for_storage_key(project_id, storage_key, config=config)

    asset_id = str(asset.get("asset_id") or asset.get("id") or "")
    proxy_base = str(config.get("asset_proxy_base_url") or "").strip()
    if proxy_base and asset_id:
        return f"{proxy_base.rstrip('/')}/{quote(asset_id, safe='')}"
    if asset_id:
        return f"/api/projects/{quote(project_id, safe='')}/assets/{quote(asset_id, safe='')}"

    value = asset.get("uri") or asset.get("path") or ""
    return f"/api/projects/{quote(project_id, safe='')}/files/{quote(str(value), safe='')}"


def public_url_for_storage_key(project_id: str, storage_key: str, *, config: Mapping[str, Any]) -> str:
    base = str(config.get("cdn_base_url") or config.get("public_base_url") or "").strip()
    if base:
        return f"{base.rstrip('/')}/{quote(storage_key, safe='/')}"
    proxy_base = str(config.get("asset_proxy_base_url") or "").strip()
    if proxy_base:
        return f"{proxy_base.rstrip('/')}/{quote(storage_key, safe='')}"
    return f"/api/projects/{quote(project_id, safe='')}/files/{quote(storage_key, safe='')}"


def _subtitle_entries(
    project_id: str,
    payload: Mapping[str, Any],
    assets: list[dict[str, Any]],
    config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    explicit = payload.get("subtitles")
    entries: list[dict[str, Any]] = []
    if isinstance(explicit, list):
        for item in explicit:
            if isinstance(item, Mapping) and item.get("format", item.get("type")) == "vtt":
                entries.append(_manifest_subtitle(project_id, item, config))
    for asset in assets:
        if asset.get("type") == AssetType.SUBTITLE_VTT:
            entries.append(_manifest_subtitle(project_id, asset, config))
    return _dedupe_manifest_entries(entries, keys=("language", "format", "url"))


def _audio_track_entries(
    project_id: str,
    payload: Mapping[str, Any],
    assets: list[dict[str, Any]],
    config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    source_audio = _first_payload_asset(payload, "source_audio", "source_audio_asset") or _first_by_type(
        assets,
        AssetType.SOURCE_AUDIO,
    )
    if source_audio:
        entries.append(
            {
                "language": "source",
                "label": "原音轨",
                "url": public_url_for_asset(source_audio, project_id=project_id, config=config),
            }
        )

    explicit = payload.get("audio_tracks")
    if isinstance(explicit, list):
        for item in explicit:
            if isinstance(item, Mapping):
                if item.get("language") == "source" and item.get("url"):
                    entries.append(
                        {
                            "language": "source",
                            "label": str(item.get("label") or "原音轨"),
                            "url": public_url_for_asset(item, project_id=project_id, config=config),
                        }
                    )
                elif item.get("type") == AssetType.TARGET_MIX_AUDIO:
                    entries.append(_manifest_audio_track(project_id, item, config))

    for asset in assets:
        if asset.get("type") == AssetType.TARGET_MIX_AUDIO:
            entries.append(_manifest_audio_track(project_id, asset, config))
    return _dedupe_manifest_entries(entries, keys=("language", "url"))


def _download_entries(
    project_id: str,
    version_id: str,
    payload: Mapping[str, Any],
    assets: list[dict[str, Any]],
    config: Mapping[str, Any],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    explicit = payload.get("downloads")
    if isinstance(explicit, list):
        for item in explicit:
            if isinstance(item, Mapping):
                download_type = str(item.get("type") or "")
                if download_type:
                    entries.append(
                        {
                            "type": download_type,
                            "label": str(item.get("label") or _download_label(download_type)),
                            "url": public_url_for_asset(item, project_id=project_id, config=config),
                        }
                    )
    for asset in assets:
        if asset.get("type") == AssetType.PACKAGE_ZIP:
            entries.append(
                {
                    "type": AssetType.PACKAGE_ZIP,
                    "label": "完整结果包",
                    "url": public_url_for_asset(asset, project_id=project_id, config=config),
                }
            )
    if not any(entry.get("type") == AssetType.PACKAGE_ZIP for entry in entries):
        entries.append(
            {
                "type": AssetType.PACKAGE_ZIP,
                "label": "完整结果包",
                "url": public_url_for_storage_key(project_id, package_path(project_id, version_id), config=config),
            }
        )
    return _dedupe_manifest_entries(entries, keys=("type", "url"))


def _manifest_subtitle(project_id: str, asset: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    language = str(asset.get("language") or "source")
    return {
        "language": language,
        "label": str(asset.get("label") or _subtitle_label(language)),
        "format": "vtt",
        "url": public_url_for_asset(asset, project_id=project_id, config=config),
    }


def _manifest_audio_track(project_id: str, asset: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    language = str(asset.get("language") or "source")
    label = str(asset.get("label") or f"{_language_label(language)} Dub")
    return {
        "language": language,
        "label": label,
        "url": public_url_for_asset(asset, project_id=project_id, config=config),
    }


def _subtitle_label(language: str) -> str:
    if language == "source":
        return "原文字幕"
    return _language_label(language)


def _language_label(language: str) -> str:
    return LANGUAGE_LABELS.get(language, language)


def _download_label(download_type: str) -> str:
    return "完整结果包" if download_type == AssetType.PACKAGE_ZIP else download_type


def _first_payload_asset(payload: Mapping[str, Any], *keys: str) -> dict[str, Any] | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, Mapping):
            return dict(value)
    return None


def _first_by_type(assets: list[dict[str, Any]], asset_type: str) -> dict[str, Any] | None:
    for asset in assets:
        if asset.get("type") == asset_type:
            return asset
    return None


def _dict_items(items: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, Mapping):
            results.append(dict(item))
    return results


def _dedupe_assets(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for asset in assets:
        key = (
            str(asset.get("asset_id") or ""),
            str(asset.get("type") or ""),
            str(asset.get("uri") or asset.get("url") or asset.get("path") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(asset)
    return deduped


def _dedupe_manifest_entries(entries: list[dict[str, Any]], *, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    seen: set[tuple[str, ...]] = set()
    deduped: list[dict[str, Any]] = []
    for entry in entries:
        key = tuple(str(entry.get(item) or "") for item in keys)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def _storage_key_for_public_url(asset: Mapping[str, Any]) -> str | None:
    storage_key = asset.get("storage_key")
    if storage_key:
        return str(storage_key)
    uri = str(asset.get("uri") or "")
    if uri.startswith("storage://private/"):
        return storage_key_from_private_uri(uri)
    return None


def _is_public_url(value: Any) -> bool:
    if not value:
        return False
    text = str(value)
    if text.startswith("storage://"):
        return False
    parsed = urlparse(text)
    return parsed.scheme in {"http", "https"} or text.startswith("/")


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
