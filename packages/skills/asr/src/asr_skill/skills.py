from __future__ import annotations

from dataclasses import is_dataclass
from pathlib import Path
from typing import Any

from asr_skill.adapters import ASRAdapterError, ASRAdapterPort, ASRRequest, adapter_from_config
from asr_skill.normalization import NormalizeOptions, normalize_speaker_timeline, normalize_transcript_segments
from asr_skill.paths import asr_source_segments_path
from asr_skill.storage import JsonAssetWriter


SKILL_VERSION = "1.0.0"


class ASRSkillRunner:
    def __init__(
        self,
        *,
        adapter: ASRAdapterPort | None = None,
        storage: JsonAssetWriter | None = None,
    ) -> None:
        self.adapter = adapter
        self.storage = storage

    def invoke(self, request: Any) -> dict[str, Any]:
        skill_name = _request_value(request, "skill_name")
        if skill_name == "asr.transcribe":
            return transcribe(request, adapter=self.adapter, storage=self.storage)
        if skill_name == "asr.diarize":
            return diarize(request, adapter=self.adapter)
        if skill_name == "transcript.normalize_segments":
            return normalize_segments(request, storage=self.storage)
        return _failed("SKILL_RUN_FAILED", f"Unsupported ASR skill: {skill_name}")


def transcribe(
    request: Any,
    *,
    adapter: ASRAdapterPort | None = None,
    storage: JsonAssetWriter | None = None,
) -> dict[str, Any]:
    project_id = _project_id(request)
    request_input = _request_input(request)
    config = _request_config(request)
    adapter = adapter or adapter_from_config(config)
    storage = storage or _storage_from_config(config)

    source_vocal = _source_vocal(request_input)
    # Also pass config (which has storage_root) so URI can be resolved to path
    if not source_vocal.get("path"):
        config_for_resolve = {**config, **request_input}
        source_vocal = _source_vocal({**request_input, **config})
    source_language = str(request_input.get("source_language") or "auto")
    enable_diarization = bool(request_input.get("enable_diarization", False))
    asr_request = ASRRequest(
        audio_asset_id=source_vocal["asset_id"],
        source_language=source_language,
        enable_diarization=enable_diarization,
        audio_uri=source_vocal.get("uri"),
        audio_path=source_vocal.get("path"),
    )
    import os as _os
    print(f"[asr.transcribe] source_vocal={source_vocal}", flush=True)
    print(f"[asr.transcribe] audio_path={asr_request.audio_path} exists={_os.path.exists(asr_request.audio_path) if asr_request.audio_path else 'N/A'}", flush=True)

    try:
        result = adapter.transcribe(asr_request)
    except ASRAdapterError as exc:
        return _failed(exc.code or "ASR_FAILED", str(exc))
    except Exception as exc:  # pragma: no cover - provider boundary
        return _failed("ASR_FAILED", str(exc))

    raw_transcript = result.raw_transcript()
    output_payload = {
        "project_id": project_id,
        "detected_language": result.detected_language,
        "raw_transcript": raw_transcript,
        "raw_segments": raw_transcript["segments"],
        "speaker_timeline": raw_transcript["speaker_timeline"],
        "provider": result.provider,
        "model": result.model,
    }
    storage_key = asr_source_segments_path(project_id)
    asset = storage.write_json(storage_key, output_payload)
    asset.update({"kind": "asr_json"})

    return _succeeded(
        outputs={
            "detected_language": result.detected_language,
            "raw_transcript": raw_transcript,
            "raw_segments": raw_transcript["segments"],
            "speaker_timeline": raw_transcript["speaker_timeline"],
            "asr_json_path": storage_key,
            "asset_id": asset["asset_id"],
            "output_refs": [asset["asset_id"]],
        },
        assets=[asset],
        usage={"provider": result.provider, "model": result.model},
    )


def diarize(
    request: Any,
    *,
    adapter: ASRAdapterPort | None = None,
) -> dict[str, Any]:
    project_id = _project_id(request)
    request_input = _request_input(request)
    config = _request_config(request)
    adapter = adapter or adapter_from_config(config)
    transcript = _raw_transcript(request_input)
    source_vocal = _source_vocal(request_input, required=False)
    asr_request = ASRRequest(
        audio_asset_id=source_vocal.get("asset_id") or "transcript",
        source_language=str(request_input.get("source_language") or "auto"),
        enable_diarization=True,
        audio_uri=source_vocal.get("uri"),
        audio_path=source_vocal.get("path"),
    )

    try:
        result = adapter.diarize(asr_request, transcript=transcript)
    except ASRAdapterError as exc:
        return _failed(exc.code or "ASR_FAILED", str(exc))
    except Exception as exc:  # pragma: no cover - provider boundary
        return _failed("ASR_FAILED", str(exc))

    normalized = normalize_speaker_timeline(
        [turn.to_dict() for turn in result.speaker_timeline],
        project_id=project_id,
    )
    return _succeeded(
        outputs=normalized,
        usage={"provider": result.provider, "model": result.model},
    )


def normalize_segments(
    request: Any,
    *,
    storage: JsonAssetWriter | None = None,
) -> dict[str, Any]:
    project_id = _project_id(request)
    request_input = _request_input(request)
    config = _request_config(request)
    storage = storage or _storage_from_config(config)
    raw_transcript = _raw_transcript(request_input)
    if not raw_transcript:
        return _failed("ASR_FAILED", "Missing raw transcript for segment normalization")

    options = NormalizeOptions(
        min_duration_ms=int(config.get("min_segment_duration_ms") or 800),
        max_duration_ms=int(config.get("max_segment_duration_ms") or 8000),
        max_merge_gap_ms=int(config.get("max_merge_gap_ms") or 600),
        max_silence_ms=int(config.get("max_silence_ms") or 1200),
    )
    locked_segments = request_input.get("locked_segments") or [
        segment for segment in request_input.get("existing_segments", []) if segment.get("locked") is True
    ]
    locked_segment_ids = [str(item) for item in request_input.get("locked_segment_ids") or []]
    reserved_segment_ids = [str(item) for item in request_input.get("existing_segment_ids") or []]
    speaker_timeline = request_input.get("speaker_timeline")
    result = normalize_transcript_segments(
        raw_transcript,
        project_id=project_id,
        source_language=str(request_input.get("source_language") or "auto"),
        speaker_timeline=speaker_timeline,
        locked_segments=locked_segments,
        locked_segment_ids=locked_segment_ids,
        reserved_segment_ids=reserved_segment_ids,
        options=options,
    )
    storage_key = asr_source_segments_path(project_id)
    asset_payload = {
        "project_id": project_id,
        "detected_language": raw_transcript.get("detected_language"),
        "segments": result["segments"],
        "skipped_locked_segment_ids": result["skipped_locked_segment_ids"],
    }
    asset = storage.write_json(storage_key, asset_payload)
    asset.update({"kind": "asr_segments_json"})

    quality_flags = result["quality_flags"]
    for segment in result["segments"]:
        quality_flags.extend(segment.get("quality_flags") or [])
    quality_flags = _dedupe_quality_flags(quality_flags)
    segment_ids = [segment["segment_id"] for segment in result["segments"]]
    return _succeeded(
        outputs={
            "segments": result["segments"],
            "segment_ids": segment_ids,
            "updated_segment_ids": segment_ids,
            "segments_version": f"segver_{project_id}_asr",
            "asr_json_path": storage_key,
            "asset_id": asset["asset_id"],
            "output_refs": [asset["asset_id"], f"segver_{project_id}_asr"],
            "skipped_locked_segment_ids": result["skipped_locked_segment_ids"],
        },
        assets=[asset],
        quality_flags=quality_flags,
    )


def _source_vocal(payload: dict[str, Any], *, required: bool = True) -> dict[str, Any]:
    value = (
        payload.get("source_vocal")
        or payload.get("source_vocal_asset")
        or payload.get("source_vocal_asset_id")
        or payload.get("vocal_asset_id")
        or payload.get("audio_asset_id")
    )
    if value is None:
        assets = payload.get("assets")
        if isinstance(assets, dict):
            value = assets.get("source_vocal") or assets.get("audio.separate_sources") or assets.get("source_vocal_asset")
    if value is None:
        if required:
            raise ValueError("source_vocal is required")
        return {}
    if isinstance(value, dict):
        asset_id = value.get("asset_id") or value.get("id") or value.get("uri") or value.get("path")
        uri = value.get("uri")
        path = value.get("path")
        # If no path but has uri, try to resolve from storage_root
        if not path and uri:
            path = _resolve_uri_to_path(uri, payload)
        return {
            "asset_id": str(asset_id),
            "uri": uri,
            "path": path,
        }
    # value is a string — could be a path or asset_id
    if "/" in str(value):
        return {"asset_id": str(value), "uri": None, "path": str(value)}
    # It's an asset_id, try to find uri/path from upstream outputs
    uri = payload.get("uri") or payload.get("source_vocal_uri")
    path = _resolve_uri_to_path(uri, payload) if uri else None
    return {"asset_id": str(value), "uri": uri, "path": path}


def _resolve_uri_to_path(uri: str, payload: dict[str, Any]) -> str | None:
    """Resolve a storage:// URI to a local file path using storage_root from payload."""
    if not uri or not uri.startswith("storage://private/"):
        return None
    key = uri.replace("storage://private/", "")
    storage_root = payload.get("storage_root") or payload.get("local_storage_root")
    if storage_root:
        return str(Path(storage_root) / key)
    return None


def _raw_transcript(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("raw_transcript") or payload.get("transcript")
    if isinstance(value, dict):
        if "raw_segments" in value and "segments" not in value:
            value = dict(value)
            value["segments"] = value["raw_segments"]
        return value
    if isinstance(value, list):
        return {"segments": value, "detected_language": payload.get("detected_language")}
    if isinstance(payload.get("raw_segments"), list):
        return {
            "segments": payload["raw_segments"],
            "detected_language": payload.get("detected_language"),
            "speaker_timeline": payload.get("speaker_timeline") or [],
        }
    return {}


def _project_id(request: Any) -> str:
    project_id = _request_value(request, "project_id") or _request_input(request).get("project_id")
    if not project_id:
        raise ValueError("project_id is required")
    return str(project_id)


def _request_input(request: Any) -> dict[str, Any]:
    value = _request_value(request, "input")
    return value if isinstance(value, dict) else {}


def _request_config(request: Any) -> dict[str, Any]:
    value = _request_value(request, "config")
    return value if isinstance(value, dict) else {}


def _request_value(request: Any, key: str) -> Any:
    if isinstance(request, dict):
        return request.get(key)
    if is_dataclass(request) or hasattr(request, key):
        return getattr(request, key, None)
    return None


def _storage_from_config(config: dict[str, Any]) -> JsonAssetWriter:
    storage_root = config.get("storage_root") or config.get("output_dir")
    return JsonAssetWriter(storage_root=storage_root)


def _succeeded(
    outputs: dict[str, Any] | None = None,
    *,
    assets: list[dict[str, Any]] | None = None,
    quality_flags: list[dict[str, Any]] | None = None,
    usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "succeeded",
        "outputs": outputs or {},
        "assets": assets or [],
        "quality_flags": quality_flags or [],
        "usage": usage or {},
        "error": None,
    }


def _failed(code: str, message: str) -> dict[str, Any]:
    if code == "PROVIDER_UNAVAILABLE":
        code = "ASR_FAILED"
    return {
        "status": "failed",
        "outputs": {},
        "assets": [],
        "quality_flags": [],
        "usage": {},
        "error": {"code": code, "message": message},
    }


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
