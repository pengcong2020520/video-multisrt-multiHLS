from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


SkillStatus = Literal["succeeded", "failed"]


@dataclass(frozen=True)
class SkillRequest:
    skill_name: str
    skill_version: str
    project_id: str
    run_id: str
    input: dict[str, Any]
    config: dict[str, Any]
    idempotency_key: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_name": self.skill_name,
            "skill_version": self.skill_version,
            "project_id": self.project_id,
            "run_id": self.run_id,
            "input": self.input,
            "config": self.config,
            "idempotency_key": self.idempotency_key,
        }


@dataclass(frozen=True)
class SkillResponse:
    status: SkillStatus
    outputs: dict[str, Any] = field(default_factory=dict)
    assets: list[Any] = field(default_factory=list)
    quality_flags: list[str] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None

    @classmethod
    def succeeded(
        cls,
        outputs: dict[str, Any] | None = None,
        *,
        assets: list[Any] | None = None,
        quality_flags: list[str] | None = None,
        usage: dict[str, Any] | None = None,
    ) -> "SkillResponse":
        return cls(
            status="succeeded",
            outputs=outputs or {},
            assets=assets or [],
            quality_flags=quality_flags or [],
            usage=usage or {},
            error=None,
        )

    @classmethod
    def failed(
        cls,
        code: str,
        message: str,
        *,
        outputs: dict[str, Any] | None = None,
        assets: list[Any] | None = None,
        quality_flags: list[str] | None = None,
    ) -> "SkillResponse":
        return cls(
            status="failed",
            outputs=outputs or {},
            assets=assets or [],
            quality_flags=quality_flags or [],
            usage={},
            error={"code": code, "message": message},
        )

    @classmethod
    def from_mapping(cls, value: "SkillResponse | dict[str, Any]") -> "SkillResponse":
        if isinstance(value, SkillResponse):
            return value
        status = value.get("status")
        if status not in {"succeeded", "failed"}:
            return cls.failed("SKILL_RUN_FAILED", "Skill response status must be succeeded or failed")
        error = value.get("error")
        if status == "failed" and not _valid_error(error):
            return cls.failed("SKILL_RUN_FAILED", "Failed skill response must include error.code and error.message")
        if status == "succeeded" and error is not None:
            return cls.failed("SKILL_RUN_FAILED", "Succeeded skill response must include error=null")
        return cls(
            status=status,
            outputs=_dict_or_empty(value.get("outputs")),
            assets=_list_or_empty(value.get("assets")),
            quality_flags=[str(flag) for flag in _list_or_empty(value.get("quality_flags"))],
            usage=_dict_or_empty(value.get("usage")),
            error=error,
        )

    def output_refs(self) -> list[str]:
        refs: list[str] = []
        for asset in self.assets:
            _collect_refs(asset, refs)
        _collect_refs(self.outputs.get("output_refs"), refs)
        _collect_refs(self.outputs.get("refs"), refs)
        for key in (
            "asset_id",
            "asset_ids",
            "version_id",
            "version_ids",
            "segments_version",
            "segment_version_id",
            "translation_version",
            "translation_versions",
            "tts_job_ids",
            "manifest_id",
            "package_id",
        ):
            _collect_refs(self.outputs.get(key), refs)
        return _dedupe(refs)


class SkillRunnerPort(Protocol):
    def invoke(self, request: SkillRequest) -> SkillResponse | dict[str, Any]:
        ...


class NoopSkillRunner:
    def invoke(self, request: SkillRequest) -> SkillResponse:
        output_key = request.skill_name.replace(".", "_")
        language = request.input.get("target_language")
        suffix = f":{language}" if language else ""
        return SkillResponse.succeeded(
            outputs={"output_refs": [f"{request.run_id}:{output_key}{suffix}"]},
            usage={"provider": request.config.get("provider"), "model": None},
        )


def input_refs(payload: dict[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in (
        "source_asset_id",
        "asset_id",
        "asset_ids",
        "segments_version",
        "segment_version_id",
        "translation_version",
        "translation_versions",
        "selected_segment_ids",
        "segment_ids",
        "tts_job_ids",
        "manifest_id",
        "package_id",
    ):
        _collect_refs(payload.get(key), refs)
    _collect_refs(payload.get("assets"), refs)
    return _dedupe(refs)


def _valid_error(error: Any) -> bool:
    return isinstance(error, dict) and bool(error.get("code")) and bool(error.get("message"))


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_or_empty(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _collect_refs(value: Any, refs: list[str]) -> None:
    if value is None:
        return
    if isinstance(value, str):
        refs.append(value)
        return
    if isinstance(value, dict):
        for key in ("ref", "id", "asset_id", "version_id", "segment_id", "translation_id", "tts_job_id"):
            item = value.get(key)
            if isinstance(item, str):
                refs.append(item)
        for item in value.values():
            if isinstance(item, (dict, list, tuple, set)):
                _collect_refs(item, refs)
            elif isinstance(item, str) and item.startswith(("asset_", "seg", "tr", "tts_", "ver_", "manifest_", "pkg_")):
                refs.append(item)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _collect_refs(item, refs)


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
