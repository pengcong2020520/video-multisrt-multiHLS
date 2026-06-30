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
        }
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
