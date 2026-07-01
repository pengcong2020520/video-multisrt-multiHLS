from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .errors import ErrorCode, MediaSkillError
from .ffmpeg import FFmpegAdapter, validate_probe_metadata
from .paths import AssetType, StoragePathResolver
from .responses import failure_response, success_response
from .separation import DemucsConfig, DemucsSourceSeparationAdapter, SourceSeparationAdapter
from .types import MediaAsset, checksum_for_file, size_bytes_for_file, stable_asset_id


DEFAULT_MAX_DURATION_MS = 180_000


def invoke(
    request: Mapping[str, Any] | Any,
    *,
    ffmpeg: FFmpegAdapter | None = None,
    separation_adapter: SourceSeparationAdapter | None = None,
    path_resolver: StoragePathResolver | None = None,
) -> dict[str, Any]:
    request_map = _request_mapping(request)
    skill_name = str(request_map.get("skill_name") or "")
    if skill_name == "media.probe":
        return probe(request_map, ffmpeg=ffmpeg, path_resolver=path_resolver)
    if skill_name == "media.extract_audio":
        return extract_audio(request_map, ffmpeg=ffmpeg, path_resolver=path_resolver)
    if skill_name == "audio.separate_sources":
        return separate_sources(request_map, separation_adapter=separation_adapter, path_resolver=path_resolver)
    return failure_response(ErrorCode.SKILL_RUN_FAILED.value, f"Unsupported skill: {skill_name}")


def probe(
    request: Mapping[str, Any] | Any,
    *,
    ffmpeg: FFmpegAdapter | None = None,
    path_resolver: StoragePathResolver | None = None,
) -> dict[str, Any]:
    request_map = _request_mapping(request)
    config = _config(request_map)
    resolver = path_resolver or _resolver_from_config(config)
    adapter = ffmpeg or FFmpegAdapter(timeout_seconds=_timeout(config, default=120))

    try:
        source_video = _asset_from_input(
            _input(request_map),
            project_id=_project_id(request_map),
            expected_type=AssetType.SOURCE_VIDEO,
            id_key="source_video_asset_id",
            asset_keys=("source_video", "source_video_asset", "asset"),
            uri_keys=("source_video_uri", "uri"),
        )
        _probe_path = resolver.input_path(source_video)
        import os as _os
        print(f"[media.probe] config={config}", flush=True)
        print(f"[media.probe] source_video={source_video}", flush=True)
        print(f"[media.probe] probe_path={_probe_path}", flush=True)
        print(f"[media.probe] file_exists={_os.path.exists(_probe_path)}", flush=True)
        metadata = adapter.probe(_probe_path)
        validate_probe_metadata(metadata, max_duration_ms=_max_duration_ms(config))
        return success_response(
            metadata.to_skill_output(),
            quality_flags=metadata.quality_flags,
            usage={"provider": "ffmpeg"},
        )
    except MediaSkillError as exc:
        return failure_response(exc.code.value, exc.message)
    except Exception as exc:  # pragma: no cover - defensive boundary for Runtime.
        return failure_response(ErrorCode.SKILL_RUN_FAILED.value, str(exc))


def extract_audio(
    request: Mapping[str, Any] | Any,
    *,
    ffmpeg: FFmpegAdapter | None = None,
    path_resolver: StoragePathResolver | None = None,
) -> dict[str, Any]:
    request_map = _request_mapping(request)
    config = _config(request_map)
    project_id = _project_id(request_map)
    run_id = _run_id(request_map)
    resolver = path_resolver or _resolver_from_config(config)
    adapter = ffmpeg or FFmpegAdapter(timeout_seconds=_timeout(config, default=300))

    try:
        source_video = _asset_from_input(
            _input(request_map),
            project_id=project_id,
            expected_type=AssetType.SOURCE_VIDEO,
            id_key="source_video_asset_id",
            asset_keys=("source_video", "source_video_asset", "asset"),
            uri_keys=("source_video_uri", "uri"),
        )
        metadata = adapter.probe(resolver.input_path(source_video))
        validate_probe_metadata(metadata, max_duration_ms=_max_duration_ms(config))

        output = resolver.output_location(project_id, AssetType.SOURCE_AUDIO)
        adapter.extract_audio(resolver.input_path(source_video), output.local_path)

        asset = _media_asset(
            project_id=project_id,
            run_id=run_id,
            asset_type=AssetType.SOURCE_AUDIO,
            uri=output.uri,
            fmt="wav",
            duration_ms=metadata.duration_ms,
            local_path=output.local_path,
        )
        return success_response(
            {
                "audio_asset_id": asset.asset_id,
                "source_audio_asset_id": asset.asset_id,
                "duration_ms": metadata.duration_ms,
                "uri": asset.uri,
            },
            assets=[asset.to_dict()],
            quality_flags=metadata.quality_flags,
            usage={"provider": "ffmpeg"},
        )
    except MediaSkillError as exc:
        return failure_response(exc.code.value, exc.message)
    except Exception as exc:  # pragma: no cover - defensive boundary for Runtime.
        return failure_response(ErrorCode.SKILL_RUN_FAILED.value, str(exc))


def separate_sources(
    request: Mapping[str, Any] | Any,
    *,
    separation_adapter: SourceSeparationAdapter | None = None,
    path_resolver: StoragePathResolver | None = None,
) -> dict[str, Any]:
    request_map = _request_mapping(request)
    config = _config(request_map)
    project_id = _project_id(request_map)
    run_id = _run_id(request_map)
    resolver = path_resolver or _resolver_from_config(config)
    adapter = separation_adapter or _demucs_from_config(config)

    try:
        payload = _input(request_map)
        mode = payload.get("mode", "vocal_background")
        if mode != "vocal_background":
            raise MediaSkillError(ErrorCode.SKILL_RUN_FAILED, f"Unsupported separation mode: {mode}")

        source_audio = _asset_from_input(
            payload,
            project_id=project_id,
            expected_type=AssetType.SOURCE_AUDIO,
            id_key="audio_asset_id",
            asset_keys=("source_audio", "audio_asset", "asset"),
            uri_keys=("source_audio_uri", "audio_uri", "uri"),
        )
        vocals_output = resolver.output_location(project_id, AssetType.SOURCE_VOCAL)
        background_output = resolver.output_location(project_id, AssetType.BACKGROUND_AUDIO)
        work_dir = Path(str(config.get("work_dir") or config.get("tmp_dir") or Path(background_output.local_path).parent / "work"))

        result = adapter.separate(
            resolver.input_path(source_audio),
            vocals_output.local_path,
            background_output.local_path,
            work_dir=work_dir,
        )
        duration_ms = _int_or_none(source_audio.get("duration_ms"))
        source_vocal = _media_asset(
            project_id=project_id,
            run_id=run_id,
            asset_type=AssetType.SOURCE_VOCAL,
            uri=vocals_output.uri,
            fmt="wav",
            duration_ms=duration_ms,
            local_path=vocals_output.local_path,
        )
        background = _media_asset(
            project_id=project_id,
            run_id=run_id,
            asset_type=AssetType.BACKGROUND_AUDIO,
            uri=background_output.uri,
            fmt="wav",
            duration_ms=duration_ms,
            local_path=background_output.local_path,
        )
        return success_response(
            {
                "source_vocal_asset_id": source_vocal.asset_id,
                "background_asset_id": background.asset_id,
                "quality_score": result.quality_score,
            },
            assets=[source_vocal.to_dict(), background.to_dict()],
            quality_flags=result.quality_flags,
            usage={"provider": adapter.provider, "model": adapter.model},
        )
    except MediaSkillError as exc:
        return failure_response(exc.code.value, exc.message)
    except Exception as exc:
        return failure_response(ErrorCode.SOURCE_SEPARATION_FAILED.value, str(exc))


def _media_asset(
    *,
    project_id: str,
    run_id: str,
    asset_type: str,
    uri: str,
    fmt: str,
    duration_ms: int | None,
    local_path: str | Path,
) -> MediaAsset:
    return MediaAsset(
        asset_id=stable_asset_id(project_id, asset_type, run_id),
        project_id=project_id,
        type=asset_type,
        language=None,
        uri=uri,
        format=fmt,
        duration_ms=duration_ms,
        size_bytes=size_bytes_for_file(local_path),
        checksum=checksum_for_file(local_path),
    )


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
    project_id = request.get("project_id")
    if not project_id:
        raise MediaSkillError(ErrorCode.SKILL_RUN_FAILED, "project_id is required")
    return str(project_id)


def _run_id(request: Mapping[str, Any]) -> str:
    run_id = request.get("run_id")
    if not run_id:
        raise MediaSkillError(ErrorCode.SKILL_RUN_FAILED, "run_id is required")
    return str(run_id)


def _resolver_from_config(config: Mapping[str, Any]) -> StoragePathResolver:
    storage_root = config.get("storage_root") or config.get("local_storage_root")
    return StoragePathResolver(storage_root=storage_root if storage_root else None)


def _demucs_from_config(config: Mapping[str, Any]) -> DemucsSourceSeparationAdapter:
    command = config.get("demucs_command")
    command_parts = tuple(command) if isinstance(command, list) else ("python", "-m", "demucs")
    model = str(config.get("demucs_model") or "htdemucs")
    quality_score = _float_or_none(config.get("quality_score"))
    return DemucsSourceSeparationAdapter(
        config=DemucsConfig(
            command=command_parts,
            model=model,
            quality_score=0.78 if quality_score is None else quality_score,
            timeout_seconds=_timeout(config, default=900),
        )
    )


def _asset_from_input(
    payload: Mapping[str, Any],
    *,
    project_id: str,
    expected_type: str,
    id_key: str,
    asset_keys: tuple[str, ...],
    uri_keys: tuple[str, ...],
) -> dict[str, Any]:
    for key in asset_keys:
        value = payload.get(key)
        if isinstance(value, Mapping):
            return _with_asset_defaults(dict(value), project_id=project_id, expected_type=expected_type)
        if isinstance(value, str) and value:
            return _with_asset_defaults({"uri": value}, project_id=project_id, expected_type=expected_type)

    assets = payload.get("assets")
    asset_id = payload.get(id_key)
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, Mapping):
                continue
            if asset_id and asset.get("asset_id") == asset_id:
                return _with_asset_defaults(dict(asset), project_id=project_id, expected_type=expected_type)
        for asset in assets:
            if isinstance(asset, Mapping) and asset.get("type") == expected_type:
                return _with_asset_defaults(dict(asset), project_id=project_id, expected_type=expected_type)

    for key in uri_keys:
        uri = payload.get(key)
        if isinstance(uri, str) and uri:
            return _with_asset_defaults({"uri": uri}, project_id=project_id, expected_type=expected_type)

    if asset_id:
        raise MediaSkillError(ErrorCode.SKILL_RUN_FAILED, f"{id_key} was provided without a resolvable asset uri")
    raise MediaSkillError(ErrorCode.SKILL_RUN_FAILED, f"{expected_type} asset is required")


def _with_asset_defaults(asset: dict[str, Any], *, project_id: str, expected_type: str) -> dict[str, Any]:
    asset.setdefault("project_id", project_id)
    asset.setdefault("type", expected_type)
    asset.setdefault("language", None)
    if not asset.get("uri"):
        raise MediaSkillError(ErrorCode.SKILL_RUN_FAILED, f"{expected_type} asset uri is required")
    return asset


def _max_duration_ms(config: Mapping[str, Any]) -> int:
    if config.get("max_duration_ms") is not None:
        return int(config["max_duration_ms"])
    if config.get("max_duration_seconds") is not None:
        return int(float(config["max_duration_seconds"]) * 1000)
    return DEFAULT_MAX_DURATION_MS


def _timeout(config: Mapping[str, Any], *, default: int) -> int:
    return int(config.get("timeout_seconds") or default)


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
