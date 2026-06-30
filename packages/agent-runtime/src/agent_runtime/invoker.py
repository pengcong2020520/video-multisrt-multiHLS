from __future__ import annotations

from hashlib import sha1
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.domain.enums import TaskStatus

from agent_runtime.context import RunContext
from agent_runtime.contracts import (
    NoopSkillRunner,
    SkillRequest,
    SkillResponse,
    SkillRunnerPort,
    input_refs,
)
from agent_runtime.registry import SkillRegistry
from agent_runtime.templates import RuntimeStep


LOCKED_WRITE_SKILLS = {
    "asr.transcribe",
    "transcript.normalize_segments",
    "localization.translate",
}


class SkillInvoker:
    def __init__(
        self,
        *,
        registry: SkillRegistry | None = None,
        runner: SkillRunnerPort | None = None,
    ) -> None:
        self.registry = registry or SkillRegistry(allow_missing_defaults=True)  # MVP: 允许跳过 DB 查找
        self.runner = runner or NoopSkillRunner()

    def invoke_with_retries(
        self,
        db: Session,
        *,
        run: models.AgentRun,
        context: RunContext,
        step: RuntimeStep,
        step_index: int,
        target_language: str | None,
    ) -> SkillResponse:
        definition = self.registry.resolve(db, step.name)
        max_attempts = definition.retry_limit + 1
        final_response: SkillResponse | None = None
        for attempt in range(max_attempts):
            request_input = context.build_skill_input(target_language=target_language)
            request_input["locked_segment_ids"] = locked_segment_ids(
                db,
                run.project_id,
                selected_segment_ids=request_input.get("selected_segment_ids"),
            )
            request = SkillRequest(
                skill_name=step.name,
                skill_version=definition.skill_version,
                project_id=run.project_id,
                run_id=run.run_id,
                input=request_input,
                config=self._skill_config(context, definition.default_provider),
                idempotency_key=self._idempotency_key(
                    run=run,
                    step=step,
                    step_index=step_index,
                    target_language=target_language,
                    context=context,
                ),
            )
            skill_run = self._start_skill_run(
                db,
                run=run,
                request=request,
                target_language=target_language,
            )
            response = self._invoke_once(request)
            response = self._guard_locked_overwrite(
                response,
                step=step,
                locked_ids=request_input["locked_segment_ids"],
            )
            self._finish_skill_run(
                skill_run,
                response,
                default_provider=definition.default_provider,
            )
            db.flush()
            final_response = response
            if response.status == "succeeded" or _non_retryable(response):
                return response
        return final_response or SkillResponse.failed("SKILL_RUN_FAILED", "Skill did not return a response")

    def _invoke_once(self, request: SkillRequest) -> SkillResponse:
        try:
            return SkillResponse.from_mapping(self.runner.invoke(request))
        except Exception as exc:  # pragma: no cover - defensive around external runner ports
            return SkillResponse.failed("SKILL_RUN_FAILED", str(exc))

    def _start_skill_run(
        self,
        db: Session,
        *,
        run: models.AgentRun,
        request: SkillRequest,
        target_language: str | None,
    ) -> models.SkillRun:
        skill_run = models.SkillRun(
            run_id=run.run_id,
            project_id=run.project_id,
            skill_name=request.skill_name,
            skill_version=request.skill_version,
            status=TaskStatus.RUNNING.value,
            target_language=target_language,
            started_at=models.utcnow(),
            input_refs=input_refs(request.input),
            output_refs=[],
            provider=request.config.get("provider"),
            model=None,
            error=None,
            quality_flags=[],
        )
        db.add(skill_run)
        db.flush()
        return skill_run

    def _finish_skill_run(
        self,
        skill_run: models.SkillRun,
        response: SkillResponse,
        *,
        default_provider: str | None,
    ) -> None:
        usage = response.usage or {}
        skill_run.status = (
            TaskStatus.SUCCEEDED.value if response.status == "succeeded" else TaskStatus.FAILED.value
        )
        skill_run.finished_at = models.utcnow()
        skill_run.output_refs = response.output_refs()
        skill_run.provider = usage.get("provider") or skill_run.provider or default_provider
        skill_run.model = usage.get("model")
        skill_run.error = response.error
        skill_run.quality_flags = response.quality_flags

    def _skill_config(self, context: RunContext, default_provider: str | None) -> dict[str, Any]:
        config = dict(context.config)
        if default_provider is not None:
            config.setdefault("provider", default_provider)
        return config

    def _idempotency_key(
        self,
        *,
        run: models.AgentRun,
        step: RuntimeStep,
        step_index: int,
        target_language: str | None,
        context: RunContext,
    ) -> str:
        fingerprint = {
            "version_id": run.version_id,
            "target_language": target_language,
            "selected_segment_ids": context.selected_segment_ids(),
        }
        encoded = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"))
        digest = sha1(encoded.encode("utf-8")).hexdigest()[:12]
        language = target_language or "all"
        return f"{run.run_id}:{step_index}:{step.name}:{language}:{digest}"

    def _guard_locked_overwrite(
        self,
        response: SkillResponse,
        *,
        step: RuntimeStep,
        locked_ids: list[str],
    ) -> SkillResponse:
        if response.status != "succeeded" or step.name not in LOCKED_WRITE_SKILLS or not locked_ids:
            return response
        locked = set(locked_ids)
        attempted = set(_response_written_segment_ids(response.outputs))
        if locked.intersection(attempted):
            return SkillResponse.failed(
                "INVALID_REQUEST",
                "Skill response attempted to overwrite locked segment",
                outputs=response.outputs,
                assets=response.assets,
                quality_flags=response.quality_flags,
            )
        return response


def locked_segment_ids(
    db: Session,
    project_id: str,
    *,
    selected_segment_ids: list[str] | None = None,
) -> list[str]:
    statement = select(models.Segment.segment_id).where(
        models.Segment.project_id == project_id,
        models.Segment.locked.is_(True),
    )
    if selected_segment_ids:
        statement = statement.where(models.Segment.segment_id.in_(selected_segment_ids))
    return list(db.execute(statement).scalars().all())


def _response_written_segment_ids(outputs: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for key in (
        "updated_segment_ids",
        "overwritten_segment_ids",
        "segment_ids",
        "translation_segment_ids",
    ):
        value = outputs.get(key)
        if isinstance(value, list):
            ids.extend(str(item) for item in value)
    for key in ("segments", "translations"):
        value = outputs.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and item.get("segment_id"):
                    ids.append(str(item["segment_id"]))
    return list(dict.fromkeys(ids))


def _non_retryable(response: SkillResponse) -> bool:
    return bool(response.error and response.error.get("code") == "INVALID_REQUEST")
