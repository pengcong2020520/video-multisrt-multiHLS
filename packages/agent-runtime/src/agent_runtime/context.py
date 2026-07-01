from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domain.enums import AgentTemplate

from agent_runtime.contracts import SkillResponse


class RunContext:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = deepcopy(data)

    @classmethod
    def initial(
        cls,
        *,
        run_id: str,
        project_id: str,
        version_id: str,
        template: AgentTemplate | str,
        source_language: str,
        target_languages: list[str],
        config: dict[str, Any] | None = None,
    ) -> "RunContext":
        config = config or {}
        return cls(
            {
                "run_id": run_id,
                "project_id": project_id,
                "version_id": version_id,
                "template": str(template),
                "source_language": source_language,
                "target_languages": target_languages,
                "current_step": None,
                "assets": {},
                "segments_version": None,
                "translation_versions": {},
                "human_checkpoints": [],
                "outputs": {},
                "config": config,
            }
        )

    @classmethod
    def from_run(cls, run: Any) -> "RunContext":
        return cls(run.run_context or {})

    def sync_to_run(self, run: Any) -> None:
        run.run_context = self.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self.data)

    @property
    def config(self) -> dict[str, Any]:
        config = self.data.setdefault("config", {})
        return config if isinstance(config, dict) else {}

    def set_current_step(self, step_name: str | None) -> None:
        self.data["current_step"] = step_name

    def mark_checkpoint(self, checkpoint: str, step_index: int) -> None:
        checkpoints = self.data.setdefault("human_checkpoints", [])
        if checkpoint not in checkpoints:
            checkpoints.append(checkpoint)
        self.data["active_checkpoint"] = checkpoint
        self.data["checkpoint_step_index"] = step_index

    def clear_checkpoint(self) -> None:
        self.data.pop("active_checkpoint", None)

    def selected_segment_ids(self) -> list[str]:
        config = self.config
        ids = config.get("segment_ids") or self.data.get("selected_segment_ids") or []
        return list(ids)

    def target_languages(self) -> list[str]:
        return list(self.data.get("target_languages") or [])

    def build_skill_input(self, *, target_language: str | None) -> dict[str, Any]:
        outputs_cache = deepcopy(self.data.get("outputs") or {})
        payload: dict[str, Any] = {
            "project_id": self.data.get("project_id"),
            "version_id": self.data.get("version_id"),
            "template": self.data.get("template"),
            "source_language": self.data.get("source_language"),
            "target_languages": self.target_languages(),
            "assets": deepcopy(self.data.get("assets") or {}),
            "segments_version": self.data.get("segments_version"),
            "translation_versions": deepcopy(self.data.get("translation_versions") or {}),
            "human_checkpoints": list(self.data.get("human_checkpoints") or []),
            "upstream_outputs": outputs_cache,
        }
        # Flatten assets dict to top-level keys so skills can find them
        # e.g. assets["source_video"] → payload["source_video"]
        assets_dict = payload.get("assets") or {}
        if isinstance(assets_dict, dict):
            for _key, _val in assets_dict.items():
                if isinstance(_val, dict) and _key not in payload:
                    payload[_key] = deepcopy(_val)
            # Also provide as list for skills that expect assets as a list
            payload["assets_list"] = list(assets_dict.values())
        # Flatten commonly-needed upstream outputs to the top level so skills that
        # read payload["raw_transcript"], payload["translations"], etc. work without
        # needing to know about the upstream_outputs namespace.
        _flatten_upstream_outputs(payload, outputs_cache, target_language)
        selected_segment_ids = self.selected_segment_ids()
        if selected_segment_ids:
            payload["selected_segment_ids"] = selected_segment_ids
            payload["segment_ids"] = selected_segment_ids
        if target_language is not None:
            payload["target_language"] = target_language
            translation_versions = payload["translation_versions"]
            if isinstance(translation_versions, dict):
                payload["translation_version"] = translation_versions.get(target_language)
        return payload

    def apply_response(
        self,
        *,
        skill_name: str,
        target_language: str | None,
        response: SkillResponse,
    ) -> None:
        outputs = response.outputs

        # Cache the full outputs keyed by skill_name (and target_language when
        # applicable) so downstream skills can read upstream payloads directly.
        outputs_cache = self.data.setdefault("outputs", {})
        cache_key = f"{skill_name}:{target_language}" if target_language else skill_name
        outputs_cache[cache_key] = deepcopy(outputs)
        # Also store under bare skill_name for skills that look up by step name
        # regardless of language (e.g. asr.transcribe → transcript.normalize_segments).
        outputs_cache[skill_name] = deepcopy(outputs)

        if "segments_version" in outputs:
            self.data["segments_version"] = outputs["segments_version"]
        if "segment_version_id" in outputs:
            self.data["segments_version"] = outputs["segment_version_id"]

        translation_versions = self.data.setdefault("translation_versions", {})
        output_translation_versions = outputs.get("translation_versions")
        if isinstance(output_translation_versions, dict):
            translation_versions.update(output_translation_versions)
        if target_language and outputs.get("translation_version"):
            translation_versions[target_language] = outputs["translation_version"]

        refs = response.output_refs()
        if refs:
            key = f"{skill_name}:{target_language}" if target_language else skill_name
            assets = self.data.setdefault("assets", {})
            assets[key] = refs

        if response.quality_flags:
            existing = self.data.setdefault("quality_flags", [])
            for flag in response.quality_flags:
                if flag not in existing:
                    existing.append(flag)


_UPSTREAM_OUTPUT_KEYS = (
    "raw_transcript",
    "raw_segments",
    "speaker_timeline",
    "detected_language",
    "segments",
    "segment_ids",
    "segments_version",
    "translations",
    "active_translations",
    "translation_versions",
    "translation_version",
    "tts_jobs",
    "tts_job_ids",
    "tts_segment_audio",
    "manifest",
    "manifest_json",
    "asset_ids",
    "subtitle_srt",
    "subtitle_vtt",
    "target_vocal",
    "target_mix_audio",
    "package_zip",
    "duration_ms",
    "detected_language",
    # Media skill asset references
    "audio_asset_id",
    "source_audio_asset_id",
    "uri",
    "source_audio_uri",
    "source_audio",
    "audio_asset",
    "vocal_asset_id",
    "background_asset_id",
    "source_vocal",
    "source_vocal_asset",
    "source_vocal_asset_id",
    # Subtitle/manifest assets
    "srt_asset_id",
    "vtt_asset_id",
)


def _flatten_upstream_outputs(
    payload: dict[str, Any],
    outputs_cache: dict[str, Any],
    target_language: str | None,
) -> None:
    """Copy commonly-needed upstream output fields to the top level of the payload.

    Skills look up data via payload["raw_transcript"], payload["translations"],
    payload["tts_jobs"], etc.  Without this flattening every downstream skill
    would need to know the upstream_outputs namespace and the cache keys.
    """
    flattened: dict[str, Any] = {}
    for cached_outputs in outputs_cache.values():
        if not isinstance(cached_outputs, dict):
            continue
        for key in _UPSTREAM_OUTPUT_KEYS:
            value = cached_outputs.get(key)
            if value is None:
                continue
            if key in flattened:
                # Prefer lists/dicts that are non-empty over earlier ones.
                if isinstance(value, (list, dict)) and value:
                    flattened[key] = value
                continue
            flattened[key] = value

    for key, value in flattened.items():
        payload.setdefault(key, value)

    # When a target language is in scope, narrow translations/active_translations
    # to that language so downstream skills (subtitle.generate, voice.synthesize)
    # don't receive translations for other languages.
    if target_language is not None:
        translations = payload.get("translations")
        if isinstance(translations, list):
            narrowed = [
                item
                for item in translations
                if isinstance(item, dict)
                and str(item.get("target_language") or "") == target_language
            ]
            if narrowed:
                payload["translations"] = narrowed
                payload["active_translations"] = narrowed
        active = payload.get("active_translations")
        if isinstance(active, list):
            narrowed_active = [
                item
                for item in active
                if isinstance(item, dict)
                and str(item.get("target_language") or "") == target_language
            ]
            if narrowed_active:
                payload["active_translations"] = narrowed_active
        tts_jobs = payload.get("tts_jobs")
        if isinstance(tts_jobs, list):
            narrowed_tts = [
                item
                for item in tts_jobs
                if isinstance(item, dict)
                and str(item.get("target_language") or "") == target_language
            ]
            if narrowed_tts:
                payload["tts_jobs"] = narrowed_tts
