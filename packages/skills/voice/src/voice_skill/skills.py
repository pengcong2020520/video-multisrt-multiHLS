from __future__ import annotations

from collections.abc import Mapping
from dataclasses import is_dataclass
from hashlib import sha256
from typing import Any

from voice_skill.adapters import TTSAdapterError, TTSAdapterPort, TTSRequest, adapter_from_config
from voice_skill.paths import tts_segment_path
from voice_skill.storage import AudioAssetWriter


SKILL_VERSION = "1.0.0"
DEFAULT_DURATION_DRIFT_RATIO = 0.20
ERROR_CODES = {
    "TTS_FAILED",
    "PROVIDER_RATE_LIMITED",
    "PROVIDER_UNAVAILABLE",
    "SKILL_RUN_FAILED",
}


class VoiceSkillRunner:
    def __init__(
        self,
        *,
        adapter: TTSAdapterPort | None = None,
        storage: AudioAssetWriter | None = None,
    ) -> None:
        self.adapter = adapter
        self.storage = storage

    def invoke(self, request: Mapping[str, Any] | Any) -> dict[str, Any]:
        request_map = _request_mapping(request)
        skill_name = str(request_map.get("skill_name") or "")
        if skill_name == "voice.synthesize":
            return synthesize(request_map, adapter=self.adapter, storage=self.storage)
        return _failed("SKILL_RUN_FAILED", f"Unsupported voice skill: {skill_name}")


def synthesize(
    request: Mapping[str, Any] | Any,
    *,
    adapter: TTSAdapterPort | None = None,
    storage: AudioAssetWriter | None = None,
) -> dict[str, Any]:
    request_map = _request_mapping(request)
    payload = _input(request_map)
    config = _config(request_map)

    try:
        project_id = _project_id(request_map)
        run_id = _run_id(request_map)
        target_language = _target_language(payload, config)
        if not target_language:
            return _failed("SKILL_RUN_FAILED", "target_language is required")
        if _voice_clone_requested(payload, config) and not _voice_clone_authorized(payload, config):
            return _failed("SKILL_RUN_FAILED", "Unauthorized voice cloning is disabled by default")

        selected_segment_ids = _selected_segment_ids(payload)
        segments = _selected_segments(_segments(payload), selected_segment_ids)
        if not segments:
            return _failed("SKILL_RUN_FAILED", "No segments selected for TTS synthesis")

        adapter = adapter or adapter_from_config(config)
        storage = storage or _storage_from_config(config)
    except TTSAdapterError as exc:
        return _failed(_normalize_error_code(exc.code), str(exc))
    except Exception as exc:
        return _failed("SKILL_RUN_FAILED", str(exc))

    translations = _translation_map(payload, target_language)
    speakers = _speaker_map(payload)
    drift_ratio = _duration_drift_ratio(config)
    style = _style(payload, config)

    tts_jobs: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []
    quality_flags: list[dict[str, Any]] = []
    first_error: dict[str, str] | None = None

    for segment in segments:
        segment_id = _segment_id(segment)
        job_id = _tts_job_id(project_id, segment_id, target_language, run_id, str(request_map.get("idempotency_key") or ""))
        target_duration_ms = _target_duration_ms(segment)
        translation = translations.get(segment_id)
        text = _translation_text(translation)
        speed = _speed(segment, translation, payload, config)

        try:
            if not text:
                raise TTSAdapterError(f"Missing active translation for segment {segment_id}", code="TTS_FAILED")
            voice_id = select_voice_id(
                segment=segment,
                translation=translation,
                speakers=speakers,
                payload=payload,
                config=config,
                target_language=target_language,
            )
            result = adapter.synthesize(
                TTSRequest(
                    target_language=target_language,
                    text=text,
                    voice_id=voice_id,
                    target_duration_ms=target_duration_ms,
                    speed=speed,
                    style=style,
                    segment_id=segment_id,
                )
            )
            storage_key = tts_segment_path(project_id, target_language, segment_id)
            asset = storage.write_audio(
                storage_key,
                result.audio,
                project_id=project_id,
                language=target_language,
                duration_ms=result.actual_duration_ms,
            )
            segment_flags = _duration_quality_flags(
                segment_id=segment_id,
                language=target_language,
                target_duration_ms=target_duration_ms,
                actual_duration_ms=result.actual_duration_ms,
                max_ratio=drift_ratio,
            )
            quality_flags.extend(segment_flags)
            assets.append(asset)
            tts_jobs.append(
                _tts_job(
                    tts_job_id=job_id,
                    project_id=project_id,
                    segment_id=segment_id,
                    target_language=target_language,
                    text=text,
                    voice_id=voice_id,
                    target_duration_ms=target_duration_ms,
                    speed=speed,
                    status="completed",
                    output_asset_id=asset["asset_id"],
                    actual_duration_ms=result.actual_duration_ms,
                    provider=result.provider,
                    provider_task_id=result.provider_task_id,
                    error=None,
                    quality_flags=segment_flags,
                )
            )
        except TTSAdapterError as exc:
            error = {"code": _normalize_error_code(exc.code), "message": str(exc)}
            first_error = first_error or error
            tts_jobs.append(
                _tts_job(
                    tts_job_id=job_id,
                    project_id=project_id,
                    segment_id=segment_id,
                    target_language=target_language,
                    text=text or "",
                    voice_id=_safe_voice_id(segment, translation, speakers, payload, config, target_language),
                    target_duration_ms=target_duration_ms,
                    speed=speed,
                    status="failed",
                    output_asset_id=None,
                    actual_duration_ms=None,
                    provider=getattr(adapter, "provider", None),
                    provider_task_id=None,
                    error=error,
                    quality_flags=[],
                )
            )
        except Exception as exc:  # pragma: no cover - defensive provider boundary.
            error = {"code": "TTS_FAILED", "message": str(exc)}
            first_error = first_error or error
            tts_jobs.append(
                _tts_job(
                    tts_job_id=job_id,
                    project_id=project_id,
                    segment_id=segment_id,
                    target_language=target_language,
                    text=text or "",
                    voice_id=_safe_voice_id(segment, translation, speakers, payload, config, target_language),
                    target_duration_ms=target_duration_ms,
                    speed=speed,
                    status="failed",
                    output_asset_id=None,
                    actual_duration_ms=None,
                    provider=getattr(adapter, "provider", None),
                    provider_task_id=None,
                    error=error,
                    quality_flags=[],
                )
            )

    outputs = _outputs(target_language=target_language, tts_jobs=tts_jobs, assets=assets)
    usage = {"provider": getattr(adapter, "provider", None), "model": getattr(adapter, "model", None)}
    if first_error:
        return _failed(
            first_error["code"],
            first_error["message"],
            outputs=outputs,
            assets=assets,
            quality_flags=_dedupe_quality_flags(quality_flags),
        )
    return _succeeded(outputs, assets=assets, quality_flags=_dedupe_quality_flags(quality_flags), usage=usage)


def select_voice_id(
    *,
    segment: dict[str, Any],
    translation: dict[str, Any] | None,
    speakers: dict[str, dict[str, Any]],
    payload: dict[str, Any],
    config: dict[str, Any],
    target_language: str,
) -> str:
    for value in (
        _non_empty_str((translation or {}).get("voice_id")),
        _non_empty_str(segment.get("voice_id")),
    ):
        if value:
            return value

    speaker_id = _non_empty_str(segment.get("speaker_id") or (translation or {}).get("speaker_id"))
    if speaker_id:
        speaker = speakers.get(speaker_id)
        if speaker:
            voice_id = _voice_from_language_map(speaker.get("target_voice_map"), target_language)
            if voice_id:
                return voice_id
        for voice_map in (
            payload.get("voice_map"),
            config.get("voice_map"),
            payload.get("speaker_voice_map"),
            config.get("speaker_voice_map"),
        ):
            voice_id = _voice_from_speaker_map(voice_map, speaker_id, target_language)
            if voice_id:
                return voice_id

    for default_map in (
        payload.get("default_voice_map"),
        config.get("default_voice_map"),
        payload.get("language_voice_map"),
        config.get("language_voice_map"),
    ):
        voice_id = _voice_from_language_map(default_map, target_language)
        if voice_id:
            return voice_id

    for key in ("default_voice_id", "voice_id"):
        voice_id = _non_empty_str(payload.get(key) or config.get(key))
        if voice_id:
            return voice_id

    raise TTSAdapterError(f"No voice_id configured for target language {target_language}", code="TTS_FAILED")


def _outputs(*, target_language: str, tts_jobs: list[dict[str, Any]], assets: list[dict[str, Any]]) -> dict[str, Any]:
    tts_job_ids = [job["tts_job_id"] for job in tts_jobs]
    asset_ids = [asset["asset_id"] for asset in assets]
    segment_ids = [job["segment_id"] for job in tts_jobs]
    return {
        "target_language": target_language,
        "tts_jobs": tts_jobs,
        "tts_job_ids": tts_job_ids,
        "asset_ids": asset_ids,
        "segment_ids": segment_ids,
        "updated_segment_ids": segment_ids,
        "output_refs": [*tts_job_ids, *asset_ids],
    }


def _tts_job(
    *,
    tts_job_id: str,
    project_id: str,
    segment_id: str,
    target_language: str,
    text: str,
    voice_id: str,
    target_duration_ms: int,
    speed: float,
    status: str,
    output_asset_id: str | None,
    actual_duration_ms: int | None,
    provider: str | None,
    provider_task_id: str | None,
    error: dict[str, str] | None,
    quality_flags: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "tts_job_id": tts_job_id,
        "project_id": project_id,
        "segment_id": segment_id,
        "target_language": target_language,
        "text": text,
        "voice_id": voice_id,
        "target_duration_ms": target_duration_ms,
        "speed": speed,
        "status": status,
        "output_asset_id": output_asset_id,
        "actual_duration_ms": actual_duration_ms,
        "provider": provider,
        "provider_task_id": provider_task_id,
        "error": error,
        "quality_flags": quality_flags,
    }


def _segments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    value = payload.get("segments") or payload.get("source_segments")
    if isinstance(value, dict):
        value = value.get("segments") or value.get("items")
    segments: list[dict[str, Any]] = []
    if isinstance(value, list):
        segments.extend(item for item in value if isinstance(item, dict))
    items = payload.get("items")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("segment"), dict):
                segments.append(item["segment"])
    return segments


def _selected_segments(segments: list[dict[str, Any]], selected_segment_ids: set[str]) -> list[dict[str, Any]]:
    if not selected_segment_ids:
        return segments
    return [segment for segment in segments if str(segment.get("segment_id") or segment.get("id")) in selected_segment_ids]


def _selected_segment_ids(payload: dict[str, Any]) -> set[str]:
    raw = payload.get("segment_ids") or payload.get("selected_segment_ids")
    if raw is None and payload.get("segment_id"):
        raw = [payload["segment_id"]]
    if raw is None:
        return set()
    if isinstance(raw, str):
        return {raw}
    return {str(item) for item in raw if item is not None}


def _translation_map(payload: dict[str, Any], target_language: str) -> dict[str, dict[str, Any]]:
    translations: dict[str, dict[str, Any]] = {}
    _collect_translations(translations, payload.get("translations"), target_language)
    _collect_translations(translations, payload.get("active_translations"), target_language)
    items = payload.get("items")
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                _collect_translations(translations, item.get("translation"), target_language)
    return translations


def _collect_translations(result: dict[str, dict[str, Any]], value: Any, target_language: str) -> None:
    if isinstance(value, dict) and isinstance(value.get("translations"), list):
        value = value["translations"]
    if isinstance(value, dict):
        for segment_id, translation in value.items():
            coerced = _coerce_translation(segment_id, translation, target_language)
            if coerced is not None:
                result[coerced["segment_id"]] = coerced
        return
    if isinstance(value, list):
        for item in value:
            coerced = _coerce_translation(None, item, target_language)
            if coerced is not None:
                result[coerced["segment_id"]] = coerced


def _coerce_translation(segment_id: str | None, value: Any, target_language: str) -> dict[str, Any] | None:
    if isinstance(value, str):
        if not segment_id:
            return None
        return {"segment_id": str(segment_id), "target_language": target_language, "text": value}
    if not isinstance(value, dict):
        return None
    language = value.get("target_language") or value.get("language")
    if language is not None and str(language) != target_language:
        return None
    if value.get("active") is False:
        return None
    if str(value.get("status") or "completed") == "failed":
        return None
    resolved_segment_id = segment_id or value.get("segment_id")
    if not resolved_segment_id:
        return None
    return {
        **value,
        "segment_id": str(resolved_segment_id),
        "target_language": target_language,
        "text": str(value.get("text") or value.get("translated_text") or ""),
    }


def _speaker_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    value = payload.get("speakers")
    if isinstance(value, dict) and isinstance(value.get("speakers"), list):
        value = value["speakers"]
    speakers: dict[str, dict[str, Any]] = {}
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and item.get("speaker_id"):
                speakers[str(item["speaker_id"])] = item
    elif isinstance(value, dict):
        for speaker_id, item in value.items():
            if isinstance(item, dict):
                speakers[str(speaker_id)] = {"speaker_id": str(speaker_id), **item}
            elif isinstance(item, str):
                speakers[str(speaker_id)] = {"speaker_id": str(speaker_id), "target_voice_map": {"default": item}}
    return speakers


def _safe_voice_id(
    segment: dict[str, Any],
    translation: dict[str, Any] | None,
    speakers: dict[str, dict[str, Any]],
    payload: dict[str, Any],
    config: dict[str, Any],
    target_language: str,
) -> str:
    try:
        return select_voice_id(
            segment=segment,
            translation=translation,
            speakers=speakers,
            payload=payload,
            config=config,
            target_language=target_language,
        )
    except TTSAdapterError:
        return ""


def _voice_from_speaker_map(value: Any, speaker_id: str, target_language: str) -> str | None:
    if not isinstance(value, dict):
        return None
    speaker_value = value.get(speaker_id)
    if isinstance(speaker_value, str):
        return speaker_value
    if isinstance(speaker_value, dict):
        return (
            _voice_from_language_map(speaker_value.get("target_voice_map"), target_language)
            or _voice_from_language_map(speaker_value, target_language)
            or _non_empty_str(speaker_value.get("voice_id"))
        )
    return None


def _voice_from_language_map(value: Any, target_language: str) -> str | None:
    if not isinstance(value, dict):
        return None
    return _non_empty_str(
        value.get(target_language)
        or value.get(target_language.lower())
        or value.get("default")
        or value.get("*")
    )


def _translation_text(translation: dict[str, Any] | None) -> str:
    if not translation:
        return ""
    return str(translation.get("text") or translation.get("translated_text") or "").strip()


def _target_duration_ms(segment: dict[str, Any]) -> int:
    if segment.get("duration_ms") is not None:
        duration = _time_to_ms(segment["duration_ms"])
        if duration > 0:
            return duration
    start_ms = _time_to_ms(segment.get("start_ms", segment.get("start", 0)))
    end_ms = _time_to_ms(segment.get("end_ms", segment.get("end", 0)))
    if end_ms <= start_ms:
        raise TTSAdapterError("segment start_ms must be less than end_ms", code="SKILL_RUN_FAILED")
    return end_ms - start_ms


def _duration_quality_flags(
    *,
    segment_id: str,
    language: str,
    target_duration_ms: int,
    actual_duration_ms: int,
    max_ratio: float,
) -> list[dict[str, Any]]:
    if target_duration_ms <= 0:
        return []
    ratio = abs(actual_duration_ms - target_duration_ms) / target_duration_ms
    if ratio <= max_ratio:
        return []
    return [
        {
            "code": "duration_drift",
            "message": f"TTS duration differs from target by more than {int(max_ratio * 100)}%",
            "severity": "warning",
            "segment_id": segment_id,
            "language": language,
        }
    ]


def _speed(
    segment: dict[str, Any],
    translation: dict[str, Any] | None,
    payload: dict[str, Any],
    config: dict[str, Any],
) -> float:
    for value in (
        (translation or {}).get("speed"),
        segment.get("speed"),
        payload.get("speed"),
        payload.get("tts_speed"),
        config.get("speed"),
        config.get("tts_speed"),
    ):
        number = _float_or_none(value)
        if number and number > 0:
            return number
    return 1.0


def _style(payload: dict[str, Any], config: dict[str, Any]) -> str | None:
    return _non_empty_str(payload.get("style") or payload.get("tts_style") or config.get("style") or config.get("tts_style"))


def _duration_drift_ratio(config: dict[str, Any]) -> float:
    value = _float_or_none(config.get("max_duration_drift_ratio") or config.get("duration_drift_ratio"))
    if value is None or value <= 0:
        return DEFAULT_DURATION_DRIFT_RATIO
    return value


def _target_language(payload: dict[str, Any], config: dict[str, Any]) -> str:
    return str(payload.get("target_language") or payload.get("language") or config.get("target_language") or "").strip()


def _segment_id(segment: dict[str, Any]) -> str:
    value = segment.get("segment_id") or segment.get("id")
    if not value:
        raise TTSAdapterError("segment_id is required", code="SKILL_RUN_FAILED")
    return str(value)


def _tts_job_id(project_id: str, segment_id: str, language: str, run_id: str, idempotency_key: str) -> str:
    digest = sha256(f"{project_id}:{segment_id}:{language}:{run_id}:{idempotency_key}".encode("utf-8")).hexdigest()
    return f"tts_{digest[:16]}"


def _storage_from_config(config: dict[str, Any]) -> AudioAssetWriter:
    storage_root = config.get("storage_root") or config.get("output_dir") or config.get("local_storage_root")
    return AudioAssetWriter(storage_root=storage_root)


def _request_mapping(request: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(request, Mapping):
        return dict(request)
    if hasattr(request, "to_dict"):
        return dict(request.to_dict())
    if is_dataclass(request) or all(hasattr(request, key) for key in ("skill_name", "project_id", "run_id")):
        return {
            "skill_name": getattr(request, "skill_name"),
            "skill_version": getattr(request, "skill_version"),
            "project_id": getattr(request, "project_id"),
            "run_id": getattr(request, "run_id"),
            "input": getattr(request, "input"),
            "config": getattr(request, "config"),
            "idempotency_key": getattr(request, "idempotency_key"),
        }
    return {}


def _input(request: Mapping[str, Any]) -> dict[str, Any]:
    payload = request.get("input")
    return dict(payload) if isinstance(payload, Mapping) else {}


def _config(request: Mapping[str, Any]) -> dict[str, Any]:
    payload = request.get("config")
    return dict(payload) if isinstance(payload, Mapping) else {}


def _project_id(request: Mapping[str, Any]) -> str:
    project_id = request.get("project_id") or _input(request).get("project_id")
    if not project_id:
        raise TTSAdapterError("project_id is required", code="SKILL_RUN_FAILED")
    return str(project_id)


def _run_id(request: Mapping[str, Any]) -> str:
    run_id = request.get("run_id")
    if not run_id:
        raise TTSAdapterError("run_id is required", code="SKILL_RUN_FAILED")
    return str(run_id)


def _voice_clone_requested(payload: dict[str, Any], config: dict[str, Any]) -> bool:
    for source in (payload, config):
        if source.get("enable_voice_clone") is True or source.get("voice_clone_enabled") is True:
            return True
        if source.get("clone_voice") is True:
            return True
        voice_clone = source.get("voice_clone")
        if isinstance(voice_clone, dict) and voice_clone.get("enabled") is True:
            return True
    return False


def _voice_clone_authorized(payload: dict[str, Any], config: dict[str, Any]) -> bool:
    return bool(
        config.get("allow_voice_clone")
        or config.get("voice_clone_authorized")
        or payload.get("voice_clone_authorized")
    )


def _time_to_ms(value: Any) -> int:
    if isinstance(value, str):
        value = float(value)
    if isinstance(value, float) and value < 1000:
        return int(round(value * 1000))
    return int(round(float(value)))


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _non_empty_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_error_code(code: str | None) -> str:
    if code in ERROR_CODES:
        return code
    return "TTS_FAILED"


def _dedupe_quality_flags(flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for flag in flags:
        key = (str(flag.get("code")), flag.get("segment_id"), flag.get("language"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(flag)
    return deduped


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


def _failed(
    code: str,
    message: str,
    *,
    outputs: dict[str, Any] | None = None,
    assets: list[dict[str, Any]] | None = None,
    quality_flags: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "status": "failed",
        "outputs": outputs or {},
        "assets": assets or [],
        "quality_flags": quality_flags or [],
        "usage": {},
        "error": {"code": _normalize_error_code(code), "message": message},
    }
