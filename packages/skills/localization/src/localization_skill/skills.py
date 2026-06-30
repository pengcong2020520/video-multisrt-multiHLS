from __future__ import annotations

from collections.abc import Mapping
from dataclasses import is_dataclass
from datetime import datetime, timezone
import hashlib
from typing import Any

from localization_skill.adapters import (
    TranslationAdapterError,
    TranslationAdapterPort,
    TranslationCandidate,
    TranslationRequest,
    TranslationResult,
    adapter_from_config,
    provider_metadata_from_config,
)
from localization_skill.paths import translation_json_path
from localization_skill.quality import dedupe_quality_flags, quality_flag, translation_quality_flags
from localization_skill.storage import JsonAssetWriter


SKILL_VERSION = "1.0.0"
SUPPORTED_TARGET_LANGUAGES = {"en-US", "zh-CN", "es-ES", "es-MX", "pt-BR"}


class LocalizationSkillRunner:
    def __init__(
        self,
        *,
        adapter: TranslationAdapterPort | None = None,
        storage: JsonAssetWriter | None = None,
    ) -> None:
        self.adapter = adapter
        self.storage = storage

    def invoke(self, request: Any) -> dict[str, Any]:
        request_map = _request_mapping(request)
        skill_name = str(request_map.get("skill_name") or "")
        if skill_name == "localization.translate":
            return translate(request_map, adapter=self.adapter, storage=self.storage)
        return _failed("SKILL_RUN_FAILED", f"Unsupported localization skill: {skill_name}")


def translate(
    request: Mapping[str, Any] | Any,
    *,
    adapter: TranslationAdapterPort | None = None,
    storage: JsonAssetWriter | None = None,
) -> dict[str, Any]:
    request_map = _request_mapping(request)
    config = _config(request_map)
    payload = _input(request_map)
    project_id = _project_id(request_map)
    run_id = str(request_map.get("run_id") or "")
    idempotency_key = str(request_map.get("idempotency_key") or "")
    storage = storage or _storage_from_config(config)

    try:
        source_language = str(payload.get("source_language") or config.get("source_language") or "auto")
        target_language = str(payload.get("target_language") or config.get("target_language") or "")
        if target_language not in SUPPORTED_TARGET_LANGUAGES:
            return _failed("TRANSLATION_FAILED", f"Unsupported target language: {target_language}")

        segments = _segments(payload)
        style = str(payload.get("style") or config.get("style") or "short_drama_localized")
        glossary = _string_dict(payload.get("glossary") or config.get("glossary") or {})
        character_notes = _string_list(payload.get("character_notes") or config.get("character_notes") or [])
        forbidden_terms = _string_list(payload.get("forbidden_terms") or config.get("forbidden_terms") or [])
        length_policy = payload.get("length_policy", config.get("length_policy", "match_duration"))
        existing_translations = _existing_translations(payload)
        locked_segment_ids = _locked_segment_ids(segments, payload)
        translatable_segments = [segment for segment in segments if str(segment.get("segment_id")) not in locked_segment_ids]
    except ValueError as exc:
        return _failed("SKILL_RUN_FAILED", str(exc))

    try:
        if translatable_segments:
            adapter = adapter or adapter_from_config(config)
            result = adapter.translate(
                TranslationRequest(
                    source_language=source_language,
                    target_language=target_language,
                    segments=translatable_segments,
                    style=style,
                    glossary=glossary,
                    character_notes=character_notes,
                    forbidden_terms=forbidden_terms,
                    length_policy=length_policy,
                )
            )
        else:
            metadata = _adapter_metadata(adapter, config)
            result = TranslationResult(
                translations=[],
                provider=metadata["provider"],
                model=metadata["model"],
                prompt_version=metadata["prompt_version"],
                usage={"tokens": 0, "cost": None},
            )
    except TranslationAdapterError as exc:
        return _failed(exc.code, str(exc))
    except Exception as exc:  # pragma: no cover - provider boundary
        return _failed("TRANSLATION_FAILED", str(exc))

    now = str(config.get("now") or _utc_now())
    generated_translations, generation_flags = _generated_translation_records(
        segments=translatable_segments,
        candidates=result.translations,
        target_language=target_language,
        style=style,
        model=result.model,
        prompt_version=result.prompt_version,
        run_id=run_id,
        idempotency_key=idempotency_key,
        updated_at=now,
        length_policy=length_policy,
    )
    merge = _merge_translation_versions(
        segments=segments,
        target_language=target_language,
        existing_translations=existing_translations,
        generated_translations=generated_translations,
        locked_segment_ids=locked_segment_ids,
    )
    locked_flags = [
        quality_flag(
            "locked_translation_skipped",
            "Locked segment was not automatically retranslated.",
            severity="info",
            segment_id=segment_id,
            language=target_language,
        )
        for segment_id in merge["skipped_locked_segment_ids"]
    ]
    quality_flags = dedupe_quality_flags(generation_flags + locked_flags)

    storage_key = translation_json_path(project_id, target_language)
    translation_version = _translation_version_id(project_id, target_language, run_id, idempotency_key)
    asset_payload = {
        "project_id": project_id,
        "target_language": target_language,
        "style": style,
        "provider": result.provider,
        "model": result.model,
        "prompt_version": result.prompt_version,
        "translation_version": translation_version,
        "updated_at": now,
        "translations": merge["active_translations"],
        "translation_versions": merge["translation_versions"],
        "quality_flags": quality_flags,
    }
    asset = storage.write_json(storage_key, asset_payload)
    asset.update({"kind": "translation_json", "language": target_language})

    usage = _usage(result)
    return _succeeded(
        outputs={
            "translations": merge["active_translations"],
            "active_translations": merge["active_translations"],
            "translation_versions": merge["translation_versions"],
            "translation_ids": [item["translation_id"] for item in merge["active_translations"]],
            "updated_translation_ids": [item["translation_id"] for item in generated_translations],
            "deactivated_translation_ids": merge["deactivated_translation_ids"],
            "skipped_locked_segment_ids": merge["skipped_locked_segment_ids"],
            "translation_json_path": storage_key,
            "translation_version": translation_version,
            "model": result.model,
            "prompt_version": result.prompt_version,
            "provider": result.provider,
            "asset_id": asset["asset_id"],
            "output_refs": [asset["asset_id"], translation_version],
        },
        assets=[asset],
        quality_flags=quality_flags,
        usage=usage,
    )


def _generated_translation_records(
    *,
    segments: list[dict[str, Any]],
    candidates: list[TranslationCandidate],
    target_language: str,
    style: str,
    model: str,
    prompt_version: str,
    run_id: str,
    idempotency_key: str,
    updated_at: str,
    length_policy: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_by_segment = {candidate.segment_id: candidate for candidate in candidates}
    records: list[dict[str, Any]] = []
    quality_flags: list[dict[str, Any]] = []
    for segment in segments:
        segment_id = str(segment.get("segment_id") or "")
        candidate = candidate_by_segment.get(segment_id)
        missing = candidate is None
        text = "" if candidate is None else candidate.text
        adapter_flags = candidate.quality_flags if candidate else []
        local_flags = translation_quality_flags(
            segment=segment,
            text=text,
            target_language=target_language,
            length_policy=length_policy,
            missing_from_provider=missing,
        )
        flags = dedupe_quality_flags(adapter_flags + local_flags)
        quality_flags.extend(flags)
        records.append(
            {
                "translation_id": _translation_id(
                    segment_id=segment_id,
                    target_language=target_language,
                    run_id=run_id,
                    idempotency_key=idempotency_key,
                    model=model,
                    prompt_version=prompt_version,
                    text=text,
                ),
                "segment_id": segment_id,
                "target_language": target_language,
                "text": text,
                "style": style,
                "model": model,
                "prompt_version": prompt_version,
                "status": "completed",
                "edited_by": None,
                "updated_at": updated_at,
                "active": True,
                "quality_flags": flags,
            }
        )
    return records, dedupe_quality_flags(quality_flags)


def _merge_translation_versions(
    *,
    segments: list[dict[str, Any]],
    target_language: str,
    existing_translations: list[dict[str, Any]],
    generated_translations: list[dict[str, Any]],
    locked_segment_ids: set[str],
) -> dict[str, Any]:
    segment_order = {
        str(segment.get("segment_id")): int(segment.get("index") or index)
        for index, segment in enumerate(segments, start=1)
    }
    generated_by_segment = {item["segment_id"]: item for item in generated_translations}
    target_segment_ids = set(segment_order)
    versions: list[dict[str, Any]] = []
    deactivated_ids: list[str] = []
    skipped_locked_ids: list[str] = []

    existing_by_segment: dict[str, list[dict[str, Any]]] = {}
    for translation in existing_translations:
        if str(translation.get("target_language") or target_language) != target_language:
            continue
        segment_id = str(translation.get("segment_id") or "")
        if not segment_id:
            continue
        existing_by_segment.setdefault(segment_id, []).append(_coerce_existing_translation(translation, target_language))

    handled_existing_segments: set[str] = set()
    for segment_id, records in existing_by_segment.items():
        handled_existing_segments.add(segment_id)
        if segment_id in locked_segment_ids:
            skipped_locked_ids.append(segment_id)
            winner_id = _preferred_existing_translation_id(records)
            for record in records:
                was_active = _is_active(record)
                record["active"] = record["translation_id"] == winner_id
                if was_active and not record["active"]:
                    deactivated_ids.append(record["translation_id"])
                versions.append(record)
            continue

        if segment_id in generated_by_segment:
            for record in records:
                if _is_active(record):
                    deactivated_ids.append(record["translation_id"])
                record["active"] = False
                versions.append(record)
            continue

        winner_id = _preferred_existing_translation_id(records)
        for record in records:
            was_active = _is_active(record)
            record["active"] = record["translation_id"] == winner_id
            if was_active and not record["active"]:
                deactivated_ids.append(record["translation_id"])
            versions.append(record)

    for segment_id in locked_segment_ids:
        if segment_id in target_segment_ids and segment_id not in handled_existing_segments:
            skipped_locked_ids.append(segment_id)

    versions.extend(generated_translations)
    versions = _enforce_single_active(versions, deactivated_ids)
    active_translations = [item for item in versions if item.get("active") is True]
    active_translations.sort(key=lambda item: (segment_order.get(item["segment_id"], 10**9), item["segment_id"]))
    versions.sort(key=lambda item: (segment_order.get(item["segment_id"], 10**9), item["segment_id"], item["translation_id"]))

    return {
        "translation_versions": versions,
        "active_translations": active_translations,
        "deactivated_translation_ids": list(dict.fromkeys(deactivated_ids)),
        "skipped_locked_segment_ids": list(dict.fromkeys(skipped_locked_ids)),
    }


def _enforce_single_active(versions: list[dict[str, Any]], deactivated_ids: list[str]) -> list[dict[str, Any]]:
    active_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for record in versions:
        if record.get("active") is not True:
            continue
        key = (record["segment_id"], record["target_language"])
        current = active_by_key.get(key)
        if current is None:
            active_by_key[key] = record
            continue
        preferred = _prefer_active_record(current, record)
        loser = current if preferred is record else record
        loser["active"] = False
        deactivated_ids.append(loser["translation_id"])
        active_by_key[key] = preferred
    return versions


def _prefer_active_record(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    if left.get("edited_by") and not right.get("edited_by"):
        return left
    if right.get("edited_by") and not left.get("edited_by"):
        return right
    return right if str(right.get("updated_at") or "") >= str(left.get("updated_at") or "") else left


def _coerce_existing_translation(translation: dict[str, Any], target_language: str) -> dict[str, Any]:
    record = dict(translation)
    record["segment_id"] = str(record.get("segment_id") or "")
    record["target_language"] = str(record.get("target_language") or target_language)
    record["translation_id"] = str(record.get("translation_id") or _existing_translation_id(record))
    record["text"] = str(record.get("text") or "")
    record.setdefault("style", "short_drama_localized")
    record.setdefault("model", None)
    record.setdefault("prompt_version", None)
    record.setdefault("status", "completed")
    record.setdefault("edited_by", None)
    record.setdefault("updated_at", _utc_now())
    if "active" not in record:
        record["active"] = True
    return record


def _preferred_existing_translation_id(records: list[dict[str, Any]]) -> str:
    active_edited = [record for record in records if _is_active(record) and record.get("edited_by")]
    if active_edited:
        return active_edited[-1]["translation_id"]
    active = [record for record in records if _is_active(record)]
    if active:
        return active[-1]["translation_id"]
    edited = [record for record in records if record.get("edited_by")]
    if edited:
        return edited[-1]["translation_id"]
    return sorted(records, key=lambda item: str(item.get("updated_at") or ""))[-1]["translation_id"]


def _is_active(record: dict[str, Any]) -> bool:
    return record.get("active") is not False


def _existing_translation_id(record: dict[str, Any]) -> str:
    seed = f"{record.get('segment_id')}:{record.get('target_language')}:{record.get('text')}:{record.get('updated_at')}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
    return f"tr_{record.get('segment_id')}_{str(record.get('target_language')).replace('-', '_')}_{digest}"


def _translation_id(
    *,
    segment_id: str,
    target_language: str,
    run_id: str,
    idempotency_key: str,
    model: str,
    prompt_version: str,
    text: str,
) -> str:
    seed = f"{segment_id}:{target_language}:{run_id}:{idempotency_key}:{model}:{prompt_version}:{text}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
    return f"tr_{segment_id}_{target_language.replace('-', '_')}_{digest}"


def _translation_version_id(project_id: str, target_language: str, run_id: str, idempotency_key: str) -> str:
    seed = f"{project_id}:{target_language}:{run_id}:{idempotency_key}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:10]
    return f"trver_{project_id}_{target_language.replace('-', '_')}_{digest}"


def _usage(result: TranslationResult) -> dict[str, Any]:
    usage = dict(result.usage)
    return {
        "provider": result.provider,
        "model": result.model,
        "tokens": _int_or_zero(usage.get("tokens")),
        "cost": usage.get("cost") if "cost" in usage else None,
    }


def _adapter_metadata(adapter: TranslationAdapterPort | None, config: dict[str, Any]) -> dict[str, Any]:
    if adapter is not None:
        return {
            "provider": adapter.provider,
            "model": adapter.model,
            "prompt_version": adapter.prompt_version,
        }
    return provider_metadata_from_config(config)


def _request_mapping(request: Mapping[str, Any] | Any) -> dict[str, Any]:
    if isinstance(request, Mapping):
        return dict(request)
    if hasattr(request, "to_dict"):
        return dict(request.to_dict())
    if is_dataclass(request) or all(hasattr(request, key) for key in ("skill_name", "project_id", "input", "config")):
        return {
            "skill_name": getattr(request, "skill_name"),
            "skill_version": getattr(request, "skill_version"),
            "project_id": getattr(request, "project_id"),
            "run_id": getattr(request, "run_id"),
            "input": getattr(request, "input"),
            "config": getattr(request, "config"),
            "idempotency_key": getattr(request, "idempotency_key"),
        }
    raise ValueError("Unsupported skill request object")


def _project_id(request: Mapping[str, Any]) -> str:
    project_id = request.get("project_id") or _input(request).get("project_id")
    if not project_id:
        raise ValueError("project_id is required")
    return str(project_id)


def _input(request: Mapping[str, Any]) -> dict[str, Any]:
    payload = request.get("input")
    return dict(payload) if isinstance(payload, Mapping) else {}


def _config(request: Mapping[str, Any]) -> dict[str, Any]:
    payload = request.get("config")
    return dict(payload) if isinstance(payload, Mapping) else {}


def _segments(payload: dict[str, Any]) -> list[dict[str, Any]]:
    value = payload.get("segments")
    if value is None:
        raise ValueError("segments is required")
    if not isinstance(value, list):
        raise ValueError("segments must be a list")
    segments = [dict(segment) for segment in value if isinstance(segment, Mapping)]
    if len(segments) != len(value):
        raise ValueError("segments must contain objects")
    for segment in segments:
        if not segment.get("segment_id"):
            raise ValueError("segment_id is required for every segment")
        segment.setdefault("locked", False)
    return segments


def _existing_translations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    value = (
        payload.get("existing_translations")
        or payload.get("translation_versions")
        or payload.get("translations")
        or []
    )
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _locked_segment_ids(segments: list[dict[str, Any]], payload: dict[str, Any]) -> set[str]:
    locked_ids = {str(segment.get("segment_id")) for segment in segments if segment.get("locked") is True}
    extra = payload.get("locked_segment_ids") or []
    if isinstance(extra, list):
        locked_ids.update(str(segment_id) for segment_id in extra)
    return {segment_id for segment_id in locked_ids if segment_id}


def _string_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _storage_from_config(config: dict[str, Any]) -> JsonAssetWriter:
    storage_root = config.get("storage_root") or config.get("output_dir")
    return JsonAssetWriter(storage_root=storage_root)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _int_or_zero(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


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
    return {
        "status": "failed",
        "outputs": {},
        "assets": [],
        "quality_flags": [],
        "usage": {},
        "error": {"code": code, "message": message},
    }
