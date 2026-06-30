from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .errors import ErrorCode, PackagingSkillError
from .ffmpeg import FFmpegAudioAdapter, VocalClip
from .manifest import build_manifest, collect_assets
from .paths import AssetType, StoragePathResolver
from .responses import failure_response, success_response
from .subtitles import render_srt, render_vtt
from .types import MediaAsset, checksum_for_file, size_bytes_for_file, stable_asset_id
from .zipper import create_package_zip


SKILL_VERSION = "1.0.0"


def invoke(
    request: Mapping[str, Any] | Any,
    *,
    ffmpeg: FFmpegAudioAdapter | None = None,
    path_resolver: StoragePathResolver | None = None,
) -> dict[str, Any]:
    request_map = _request_mapping(request)
    skill_name = str(request_map.get("skill_name") or "")
    if skill_name == "subtitle.generate":
        return generate_subtitles(request_map, path_resolver=path_resolver)
    if skill_name == "audio.stitch_vocals":
        return stitch_vocals(request_map, ffmpeg=ffmpeg, path_resolver=path_resolver)
    if skill_name == "audio.mix":
        return mix_audio(request_map, ffmpeg=ffmpeg, path_resolver=path_resolver)
    if skill_name == "package.manifest":
        return make_manifest(request_map)
    if skill_name == "package.zip":
        return package_zip(request_map, path_resolver=path_resolver)
    return failure_response(ErrorCode.SKILL_RUN_FAILED.value, f"Unsupported skill: {skill_name}")


def generate_subtitles(
    request: Mapping[str, Any] | Any,
    *,
    path_resolver: StoragePathResolver | None = None,
) -> dict[str, Any]:
    request_map = _request_mapping(request)
    project_id = _project_id(request_map)
    run_id = _run_id(request_map)
    payload = _input(request_map)
    config = _config(request_map)
    resolver = path_resolver or _resolver_from_config(config)

    try:
        target_language = _target_language(payload, config)
        segments = _segments(payload)
        translations = payload.get("active_translations") or payload.get("translations") or {}
        max_line_chars = int(config.get("max_subtitle_line_chars") or 42)
        srt_result = render_srt(segments, translations, target_language, max_line_chars=max_line_chars)
        vtt_result = render_vtt(segments, translations, target_language, max_line_chars=max_line_chars)

        srt_output = resolver.output_location(project_id, AssetType.SUBTITLE_SRT, language=target_language)
        vtt_output = resolver.output_location(project_id, AssetType.SUBTITLE_VTT, language=target_language)
        srt_output.local_path.write_text(srt_result.content, encoding="utf-8")
        vtt_output.local_path.write_text(vtt_result.content, encoding="utf-8")

        duration_ms = _duration_from_segments(segments)
        srt_asset = _media_asset(
            project_id=project_id,
            run_id=run_id,
            asset_type=AssetType.SUBTITLE_SRT,
            language=target_language,
            uri=srt_output.uri,
            fmt="srt",
            duration_ms=duration_ms,
            local_path=srt_output.local_path,
            storage_key=srt_output.storage_key,
        )
        vtt_asset = _media_asset(
            project_id=project_id,
            run_id=run_id,
            asset_type=AssetType.SUBTITLE_VTT,
            language=target_language,
            uri=vtt_output.uri,
            fmt="vtt",
            duration_ms=duration_ms,
            local_path=vtt_output.local_path,
            storage_key=vtt_output.storage_key,
        )
        assets = [srt_asset.to_dict(), vtt_asset.to_dict()]
        return success_response(
            {
                "subtitle_srt_asset_id": srt_asset.asset_id,
                "subtitle_vtt_asset_id": vtt_asset.asset_id,
                "subtitle_srt": assets[0],
                "subtitle_vtt": assets[1],
                "srt_uri": srt_asset.uri,
                "vtt_uri": vtt_asset.uri,
                "output_refs": [srt_asset.asset_id, vtt_asset.asset_id],
            },
            assets=assets,
            quality_flags=_dedupe_quality_flags(srt_result.quality_flags + vtt_result.quality_flags),
            usage={"provider": "local"},
        )
    except PackagingSkillError as exc:
        return failure_response(exc.code.value, exc.message)
    except Exception as exc:
        return failure_response(ErrorCode.PACKAGE_FAILED.value, str(exc))


def stitch_vocals(
    request: Mapping[str, Any] | Any,
    *,
    ffmpeg: FFmpegAudioAdapter | None = None,
    path_resolver: StoragePathResolver | None = None,
) -> dict[str, Any]:
    request_map = _request_mapping(request)
    project_id = _project_id(request_map)
    run_id = _run_id(request_map)
    payload = _input(request_map)
    config = _config(request_map)
    resolver = path_resolver or _resolver_from_config(config)
    adapter = ffmpeg or FFmpegAudioAdapter(timeout_seconds=_timeout(config, default=600))

    try:
        target_language = _target_language(payload, config)
        clips, quality_flags = _vocal_clips(payload, resolver)
        if not clips:
            raise PackagingSkillError(ErrorCode.MIXING_FAILED, "No usable TTS segment audio was provided")
        output = resolver.output_location(project_id, AssetType.TARGET_VOCAL, language=target_language)
        adapter.stitch_vocals(
            clips,
            output.local_path,
            sample_rate=int(config.get("sample_rate") or 48000),
            channels=int(config.get("channels") or 2),
        )
        duration_ms = max(clip.start_ms + (clip.actual_duration_ms or clip.segment_duration_ms) for clip in clips)
        asset = _media_asset(
            project_id=project_id,
            run_id=run_id,
            asset_type=AssetType.TARGET_VOCAL,
            language=target_language,
            uri=output.uri,
            fmt="wav",
            duration_ms=duration_ms,
            local_path=output.local_path,
            storage_key=output.storage_key,
        )
        return success_response(
            {
                "target_vocal_asset_id": asset.asset_id,
                "target_vocal": asset.to_dict(),
                "uri": asset.uri,
                "output_refs": [asset.asset_id],
            },
            assets=[asset.to_dict()],
            quality_flags=quality_flags,
            usage={"provider": "ffmpeg"},
        )
    except PackagingSkillError as exc:
        return failure_response(exc.code.value, exc.message)
    except Exception as exc:
        return failure_response(ErrorCode.MIXING_FAILED.value, str(exc))


def mix_audio(
    request: Mapping[str, Any] | Any,
    *,
    ffmpeg: FFmpegAudioAdapter | None = None,
    path_resolver: StoragePathResolver | None = None,
) -> dict[str, Any]:
    request_map = _request_mapping(request)
    project_id = _project_id(request_map)
    run_id = _run_id(request_map)
    payload = _input(request_map)
    config = _config(request_map)
    resolver = path_resolver or _resolver_from_config(config)
    adapter = ffmpeg or FFmpegAudioAdapter(timeout_seconds=_timeout(config, default=600))

    try:
        target_language = _target_language(payload, config)
        target_vocal = _asset_from_payload(payload, AssetType.TARGET_VOCAL, "target_vocal", "target_vocal_asset")
        background_audio = _asset_from_payload(
            payload,
            AssetType.BACKGROUND_AUDIO,
            "background_audio",
            "background_audio_asset",
            "background",
        )
        output = resolver.output_location(project_id, AssetType.TARGET_MIX_AUDIO, language=target_language)
        adapter.mix(
            resolver.input_path(background_audio),
            resolver.input_path(target_vocal),
            output.local_path,
            sample_rate=int(config.get("sample_rate") or 48000),
            channels=int(config.get("channels") or 2),
            background_volume=float(config.get("background_volume") or 1.0),
            vocal_volume=float(config.get("vocal_volume") or 1.0),
            bitrate=str(config.get("audio_bitrate") or "192k"),
        )
        duration_ms = _int_or_none(background_audio.get("duration_ms")) or _int_or_none(target_vocal.get("duration_ms"))
        asset = _media_asset(
            project_id=project_id,
            run_id=run_id,
            asset_type=AssetType.TARGET_MIX_AUDIO,
            language=target_language,
            uri=output.uri,
            fmt="m4a",
            duration_ms=duration_ms,
            local_path=output.local_path,
            storage_key=output.storage_key,
        )
        return success_response(
            {
                "target_mix_audio_asset_id": asset.asset_id,
                "target_mix_audio": asset.to_dict(),
                "uri": asset.uri,
                "output_refs": [asset.asset_id],
            },
            assets=[asset.to_dict()],
            usage={"provider": "ffmpeg"},
        )
    except PackagingSkillError as exc:
        return failure_response(exc.code.value, exc.message)
    except Exception as exc:
        return failure_response(ErrorCode.MIXING_FAILED.value, str(exc))


def make_manifest(request: Mapping[str, Any] | Any) -> dict[str, Any]:
    request_map = _request_mapping(request)
    project_id = _project_id(request_map)
    payload = _input(request_map)
    config = _config(request_map)
    try:
        version_id = _version_id(payload, request_map)
        manifest = build_manifest(project_id, version_id, payload, config=config)
        return success_response(
            {
                "manifest": manifest,
                "manifest_json": manifest,
                "version_id": version_id,
                "output_refs": [version_id],
            },
            usage={"provider": "local"},
        )
    except PackagingSkillError as exc:
        return failure_response(exc.code.value, exc.message)
    except Exception as exc:
        return failure_response(ErrorCode.PACKAGE_FAILED.value, str(exc))


def package_zip(
    request: Mapping[str, Any] | Any,
    *,
    path_resolver: StoragePathResolver | None = None,
) -> dict[str, Any]:
    request_map = _request_mapping(request)
    project_id = _project_id(request_map)
    run_id = _run_id(request_map)
    payload = _input(request_map)
    config = _config(request_map)
    resolver = path_resolver or _resolver_from_config(config)

    try:
        version_id = _version_id(payload, request_map)
        output = resolver.output_location(project_id, AssetType.PACKAGE_ZIP, version_id=version_id)
        manifest = payload.get("manifest")
        if not isinstance(manifest, Mapping):
            package_asset_stub = {
                "type": AssetType.PACKAGE_ZIP,
                "uri": output.uri,
                "storage_key": output.storage_key,
                "format": "zip",
            }
            manifest_payload = dict(payload)
            manifest_payload.setdefault("package_zip", package_asset_stub)
            manifest = build_manifest(project_id, version_id, manifest_payload, config=config)
        assets = collect_assets(payload)
        include_intermediate_assets = bool(payload.get("include_intermediate_assets", True))
        entries = create_package_zip(
            project_id=project_id,
            manifest=manifest,
            assets=assets,
            output_path=output.local_path,
            resolver=resolver,
            include_intermediate_assets=include_intermediate_assets,
        )
        asset = _media_asset(
            project_id=project_id,
            run_id=run_id,
            asset_type=AssetType.PACKAGE_ZIP,
            language=None,
            uri=output.uri,
            fmt="zip",
            duration_ms=None,
            local_path=output.local_path,
            storage_key=output.storage_key,
        )
        return success_response(
            {
                "package_zip_asset_id": asset.asset_id,
                "package_zip": asset.to_dict(),
                "zip_entries": entries,
                "uri": asset.uri,
                "output_refs": [asset.asset_id],
            },
            assets=[asset.to_dict()],
            usage={"provider": "local"},
        )
    except PackagingSkillError as exc:
        return failure_response(exc.code.value, exc.message)
    except Exception as exc:
        return failure_response(ErrorCode.PACKAGE_FAILED.value, str(exc))


def _media_asset(
    *,
    project_id: str,
    run_id: str,
    asset_type: str,
    language: str | None,
    uri: str,
    fmt: str,
    duration_ms: int | None,
    local_path: str | Path,
    storage_key: str,
) -> MediaAsset:
    return MediaAsset(
        asset_id=stable_asset_id(project_id, asset_type, run_id, language=language),
        project_id=project_id,
        type=asset_type,
        language=language,
        uri=uri,
        format=fmt,
        duration_ms=duration_ms,
        size_bytes=size_bytes_for_file(local_path),
        checksum=checksum_for_file(local_path),
        storage_key=storage_key,
    )


def _vocal_clips(payload: Mapping[str, Any], resolver: StoragePathResolver) -> tuple[list[VocalClip], list[dict[str, Any]]]:
    segments = _segments(payload)
    audio_by_segment = _tts_audio_by_segment(payload)
    clips: list[VocalClip] = []
    quality_flags: list[dict[str, Any]] = []
    for segment in sorted(segments, key=lambda item: (_int_ms(item.get("start_ms")), int(item.get("index") or 0))):
        segment_id = str(segment.get("segment_id") or "")
        asset = audio_by_segment.get(segment_id)
        if not asset:
            quality_flags.append(
                {
                    "code": "MISSING_TTS_AUDIO",
                    "segment_id": segment_id,
                    "message": "No TTS segment audio was provided for this segment",
                }
            )
            continue
        start_ms = _int_ms(segment.get("start_ms"))
        duration_ms = max(0, _int_ms(segment.get("end_ms")) - start_ms)
        actual_duration_ms = _int_or_none(asset.get("actual_duration_ms") or asset.get("duration_ms"))
        clip = VocalClip(
            segment_id=segment_id,
            input_path=resolver.input_path(asset),
            start_ms=start_ms,
            segment_duration_ms=duration_ms,
            actual_duration_ms=actual_duration_ms,
        )
        if clip.is_longer_than_segment:
            quality_flags.append(
                {
                    "code": "TTS_LONGER_THAN_SEGMENT",
                    "segment_id": segment_id,
                    "message": "TTS audio is longer than the segment duration",
                    "actual_duration_ms": actual_duration_ms,
                    "target_duration_ms": duration_ms,
                }
            )
        clips.append(clip)
    return clips, quality_flags


def _tts_audio_by_segment(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw_items = (
        payload.get("tts_segment_audio")
        or payload.get("tts_segment_audios")
        or payload.get("tts_assets")
        or payload.get("tts_jobs")
        or []
    )
    if isinstance(raw_items, Mapping):
        items = raw_items.values()
    elif isinstance(raw_items, (list, tuple, set)):
        items = raw_items
    else:
        items = []
    by_segment: dict[str, dict[str, Any]] = {}
    for raw_item in items:
        if not isinstance(raw_item, Mapping):
            continue
        item = dict(raw_item)
        nested_asset = item.get("asset") or item.get("output_asset") or item.get("media_asset")
        asset = dict(nested_asset) if isinstance(nested_asset, Mapping) else dict(item)
        segment_id = str(item.get("segment_id") or asset.get("segment_id") or "")
        if not segment_id:
            continue
        asset["segment_id"] = segment_id
        asset.setdefault("type", AssetType.TTS_SEGMENT_AUDIO)
        if item.get("output_asset_id") and not asset.get("asset_id"):
            asset["asset_id"] = item["output_asset_id"]
        if item.get("output_asset_uri") and not asset.get("uri"):
            asset["uri"] = item["output_asset_uri"]
        if item.get("path") and not asset.get("path"):
            asset["path"] = item["path"]
        if item.get("actual_duration_ms") is not None:
            asset["actual_duration_ms"] = item["actual_duration_ms"]
        if asset.get("duration_ms") is None and item.get("duration_ms") is not None:
            asset["duration_ms"] = item["duration_ms"]
        by_segment[segment_id] = asset
    return by_segment


def _request_mapping(request: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(request, Mapping):
        return dict(request)
    if hasattr(request, "to_dict"):
        return dict(request.to_dict())
    return {
        "skill_name": getattr(request, "skill_name"),
        "skill_version": getattr(request, "skill_version"),
        "project_id": getattr(request, "project_id"),
        "run_id": getattr(request, "run_id"),
        "input": getattr(request, "input"),
        "config": getattr(request, "config"),
        "idempotency_key": getattr(request, "idempotency_key"),
    }


def _input(request: Mapping[str, Any]) -> dict[str, Any]:
    payload = request.get("input")
    return dict(payload) if isinstance(payload, Mapping) else {}


def _config(request: Mapping[str, Any]) -> dict[str, Any]:
    payload = request.get("config")
    return dict(payload) if isinstance(payload, Mapping) else {}


def _project_id(request: Mapping[str, Any]) -> str:
    project_id = request.get("project_id") or _input(request).get("project_id")
    if not project_id:
        raise PackagingSkillError(ErrorCode.SKILL_RUN_FAILED, "project_id is required")
    return str(project_id)


def _run_id(request: Mapping[str, Any]) -> str:
    run_id = request.get("run_id")
    if not run_id:
        raise PackagingSkillError(ErrorCode.SKILL_RUN_FAILED, "run_id is required")
    return str(run_id)


def _target_language(payload: Mapping[str, Any], config: Mapping[str, Any]) -> str:
    language = payload.get("target_language") or payload.get("language") or config.get("target_language")
    if not language:
        raise PackagingSkillError(ErrorCode.SKILL_RUN_FAILED, "target_language is required")
    return str(language)


def _version_id(payload: Mapping[str, Any], request: Mapping[str, Any]) -> str:
    version_id = payload.get("version_id") or request.get("version_id")
    if not version_id:
        raise PackagingSkillError(ErrorCode.SKILL_RUN_FAILED, "version_id is required")
    return str(version_id)


def _segments(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    segments = payload.get("segments")
    if not isinstance(segments, list) or not segments:
        raise PackagingSkillError(ErrorCode.SKILL_RUN_FAILED, "segments are required")
    return [dict(segment) for segment in segments if isinstance(segment, Mapping)]


def _asset_from_payload(payload: Mapping[str, Any], asset_type: str, *keys: str) -> dict[str, Any]:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, Mapping):
            return dict(value)
    assets = collect_assets(payload)
    for asset in assets:
        if asset.get("type") == asset_type:
            return asset
    raise PackagingSkillError(ErrorCode.MIXING_FAILED, f"{asset_type} asset is required")


def _duration_from_segments(segments: list[dict[str, Any]]) -> int | None:
    end_times = [_int_ms(segment.get("end_ms")) for segment in segments]
    return max(end_times) if end_times else None


def _resolver_from_config(config: Mapping[str, Any]) -> StoragePathResolver:
    storage_root = config.get("storage_root") or config.get("local_storage_root")
    return StoragePathResolver(storage_root=storage_root if storage_root else None)


def _timeout(config: Mapping[str, Any], *, default: int) -> int:
    return int(config.get("timeout_seconds") or default)


def _int_ms(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dedupe_quality_flags(flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for flag in flags:
        key = (str(flag.get("code")), flag.get("segment_id"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(flag)
    return deduped
