from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app import models
from app.domain.enums import AgentRunStatus, AgentTemplate, ProjectStatus, TaskStatus
from app.domain.state_machine import validate_agent_run_transition, validate_project_transition

from agent_runtime.context import RunContext
from agent_runtime.contracts import SkillResponse, SkillRunnerPort
from agent_runtime.invoker import SkillInvoker
from agent_runtime.persister import NoopResponsePersister, ResponsePersisterPort
from agent_runtime.registry import SkillRegistry
from agent_runtime.templates import (
    RuntimeStep,
    runtime_plan_for_template,
    task_requires_language,
)


class QueuePort(Protocol):
    def enqueue(self, queue_name: str, payload: dict[str, Any]) -> str:
        ...


class AgentRuntime:
    def __init__(
        self,
        queue: QueuePort | None = None,
        *,
        skill_runner: SkillRunnerPort | None = None,
        registry: SkillRegistry | None = None,
        persister: ResponsePersisterPort | None = None,
        auto_execute: bool = False,
    ) -> None:
        self.queue = queue
        self.auto_execute = auto_execute
        self.persister = persister or NoopResponsePersister()
        self.invoker = SkillInvoker(registry=registry, runner=skill_runner)

    def create_run(
        self,
        db: Session,
        project: models.Project,
        *,
        version: models.Version,
        template: AgentTemplate,
        created_by: str,
        target_languages: list[str],
        context: dict[str, Any],
    ) -> models.AgentRun:
        template = AgentTemplate(template)
        target_languages = list(dict.fromkeys(target_languages))
        run = models.AgentRun(
            project_id=project.project_id,
            version_id=version.version_id,
            template=template.value,
            status=AgentRunStatus.PENDING.value,
            current_step=None,
            source_language=project.source_language,
            target_languages=target_languages,
            run_context={},
            created_by=created_by,
        )
        db.add(run)
        db.flush()

        run_context = RunContext.initial(
            run_id=run.run_id,
            project_id=project.project_id,
            version_id=version.version_id,
            template=template.value,
            source_language=project.source_language,
            target_languages=target_languages,
            config=context,
        )
        # Seed RunContext with source_video asset from DB so media.probe can find it
        from sqlalchemy import select as _select
        source_asset = (
            db.execute(
                _select(models.MediaAsset).where(
                    models.MediaAsset.project_id == project.project_id,
                    models.MediaAsset.type == "source_video",
                ).order_by(models.MediaAsset.created_at.desc())
            ).scalars().first()
        )
        if source_asset is not None:
            assets = run_context.data.setdefault("assets", {})
            assets["source_video"] = {
                "asset_id": source_asset.asset_id,
                "uri": source_asset.uri,
                "format": source_asset.format,
                "type": "source_video",
            }
        run_context.sync_to_run(run)
        self._create_tasks(db, run=run, context=run_context)
        self._enqueue(
            "agent_runs",
            {
                "run_id": run.run_id,
                "project_id": project.project_id,
                "version_id": version.version_id,
                "template": template.value,
            },
        )
        if self.auto_execute:
            return self.execute(db, run)
        return run

    def continue_run(self, db: Session, run: models.AgentRun) -> models.AgentRun:
        if AgentRunStatus(run.status) != AgentRunStatus.WAITING_HUMAN:
            raise ValueError("Only waiting_human runs can be continued")
        self._set_agent_status(run, AgentRunStatus.RUNNING)
        run.checkpoint = None
        context = RunContext.from_run(run)
        context.clear_checkpoint()
        context.sync_to_run(run)

        project = db.get(models.Project, run.project_id)
        if project is not None:
            self._set_project_status(project, ProjectStatus.GENERATING)

        self._enqueue("agent_runs", {"run_id": run.run_id, "action": "continue"})
        if self.auto_execute:
            return self.execute(db, run, resume_after_checkpoint=True)
        return run

    def execute(
        self,
        db: Session,
        run: models.AgentRun,
        *,
        resume_after_checkpoint: bool = False,
    ) -> models.AgentRun:
        context = RunContext.from_run(run)
        plan = runtime_plan_for_template(run.template, context.config)
        start_index = self._start_index(context, resume_after_checkpoint=resume_after_checkpoint)

        self._set_agent_status(run, AgentRunStatus.RUNNING)
        project = db.get(models.Project, run.project_id)
        if project is not None:
            desired_project_status = (
                ProjectStatus.GENERATING
                if resume_after_checkpoint
                or AgentTemplate(run.template) in {AgentTemplate.RERUN_SEGMENTS, AgentTemplate.PACKAGE_ONLY}
                else ProjectStatus.PROCESSING
            )
            if project.status != ProjectStatus.GENERATING.value:
                self._set_project_status(project, desired_project_status)

        for step_index, step in enumerate(plan[start_index:], start=start_index):
            if step.is_checkpoint:
                return self._pause_for_checkpoint(
                    db,
                    run=run,
                    project=project,
                    context=context,
                    step=step,
                    step_index=step_index,
                )

            run.current_step = step.name
            context.set_current_step(step.name)
            context.sync_to_run(run)
            db.flush()

            for target_language in self._target_languages_for_step(run, step):
                response = self.invoker.invoke_with_retries(
                    db,
                    run=run,
                    context=context,
                    step=step,
                    step_index=step_index,
                    target_language=target_language,
                )
                if response.status == "failed":
                    return self._fail_run(run=run, project=project, context=context, response=response)
                context.apply_response(
                    skill_name=step.name,
                    target_language=target_language,
                    response=response,
                )
                self.persister.persist(
                    db,
                    project_id=run.project_id,
                    run_id=run.run_id,
                    skill_name=step.name,
                    target_language=target_language,
                    response=response,
                )
                context.sync_to_run(run)
                run.quality_flags = context.data.get("quality_flags", [])
                db.flush()

        run.current_step = None
        context.set_current_step(None)
        context.sync_to_run(run)
        self._set_agent_status(run, AgentRunStatus.SUCCEEDED)
        if project is not None:
            self._set_project_status(project, ProjectStatus.COMPLETED)
        db.flush()
        return run

    def rerun_language(
        self,
        db: Session,
        project_id: str,
        target_language: str,
        steps: list[str] | None = None,
        *,
        created_by: str | None = None,
    ) -> models.AgentRun:
        project = _project_or_raise(db, project_id)
        version = _active_version_or_raise(db, project)
        self._set_project_status(project, ProjectStatus.GENERATING)
        return self.create_run(
            db,
            project,
            version=version,
            template=AgentTemplate.RERUN_SEGMENTS,
            created_by=created_by or project.created_by,
            target_languages=[target_language],
            context={"scope": "language", "steps": steps or ["tts", "mix"]},
        )

    def rerun_segments(
        self,
        db: Session,
        project_id: str,
        target_language: str,
        segment_ids: list[str],
        steps: list[str] | None = None,
        *,
        created_by: str | None = None,
    ) -> models.AgentRun:
        project = _project_or_raise(db, project_id)
        version = _active_version_or_raise(db, project)
        self._set_project_status(project, ProjectStatus.GENERATING)
        return self.create_run(
            db,
            project,
            version=version,
            template=AgentTemplate.RERUN_SEGMENTS,
            created_by=created_by or project.created_by,
            target_languages=[target_language],
            context={
                "scope": "segments",
                "target_language": target_language,
                "segment_ids": list(dict.fromkeys(segment_ids)),
                "steps": steps or ["tts", "mix"],
            },
        )

    def get_run_status(self, db: Session, run_id: str) -> dict[str, Any]:
        run = db.get(models.AgentRun, run_id)
        if run is None:
            raise LookupError(f"AgentRun not found: {run_id}")
        skill_runs = (
            db.execute(
                select(models.SkillRun)
                .where(models.SkillRun.run_id == run.run_id)
                .order_by(models.SkillRun.started_at, models.SkillRun.skill_run_id)
            )
            .scalars()
            .all()
        )
        return {
            "agent_run": run,
            "skill_runs": skill_runs,
            "current_checkpoint": run.checkpoint,
            "quality_flags": run.quality_flags,
            "run_context": run.run_context,
        }

    def createRun(self, *args: Any, **kwargs: Any) -> models.AgentRun:
        return self.create_run(*args, **kwargs)

    def continueRun(self, *args: Any, **kwargs: Any) -> models.AgentRun:
        return self.continue_run(*args, **kwargs)

    def rerunLanguage(self, *args: Any, **kwargs: Any) -> models.AgentRun:
        return self.rerun_language(*args, **kwargs)

    def rerunSegments(self, *args: Any, **kwargs: Any) -> models.AgentRun:
        return self.rerun_segments(*args, **kwargs)

    def getRunStatus(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return self.get_run_status(*args, **kwargs)

    def _create_tasks(self, db: Session, *, run: models.AgentRun, context: RunContext) -> None:
        for step in runtime_plan_for_template(run.template, context.config):
            if step.task_type is None:
                continue
            target_languages = run.target_languages if task_requires_language(step.task_type) else [None]
            for target_language in target_languages:
                db.add(
                    models.Task(
                        project_id=run.project_id,
                        run_id=run.run_id,
                        type=step.task_type.value,
                        status=TaskStatus.PENDING.value,
                        target_language=target_language,
                    )
                )

    def _pause_for_checkpoint(
        self,
        db: Session,
        *,
        run: models.AgentRun,
        project: models.Project | None,
        context: RunContext,
        step: RuntimeStep,
        step_index: int,
    ) -> models.AgentRun:
        run.current_step = step.name
        run.checkpoint = step.checkpoint
        context.set_current_step(step.name)
        context.mark_checkpoint(step.checkpoint or step.name, step_index)
        context.sync_to_run(run)
        self._set_agent_status(run, AgentRunStatus.WAITING_HUMAN)
        if project is not None:
            self._set_project_status(project, ProjectStatus.PROOFREADING)
        db.flush()
        return run

    def _fail_run(
        self,
        *,
        run: models.AgentRun,
        project: models.Project | None,
        context: RunContext,
        response: SkillResponse,
    ) -> models.AgentRun:
        if response.error:
            errors = context.data.setdefault("errors", [])
            errors.append(response.error)
        context.sync_to_run(run)
        self._set_agent_status(run, AgentRunStatus.FAILED)
        if project is not None:
            self._set_project_status(project, ProjectStatus.FAILED)
        return run

    def _target_languages_for_step(
        self,
        run: models.AgentRun,
        step: RuntimeStep,
    ) -> list[str | None]:
        if step.language_scope == "target":
            return list(run.target_languages)
        return [None]

    def _set_agent_status(self, run: models.AgentRun, status: AgentRunStatus) -> None:
        validate_agent_run_transition(run.status, status)
        run.status = status.value

    def _set_project_status(self, project: models.Project, status: ProjectStatus) -> None:
        validate_project_transition(project.status, status)
        project.status = status.value

    def _enqueue(self, queue_name: str, payload: dict[str, Any]) -> None:
        if self.queue is not None:
            self.queue.enqueue(queue_name, payload)

    def _start_index(self, context: RunContext, *, resume_after_checkpoint: bool) -> int:
        if not resume_after_checkpoint:
            return int(context.data.get("next_step_index", 0) or 0)
        checkpoint_index = context.data.get("checkpoint_step_index")
        if checkpoint_index is None:
            return 0
        return int(checkpoint_index) + 1


def _project_or_raise(db: Session, project_id: str) -> models.Project:
    project = db.get(models.Project, project_id)
    if project is None:
        raise LookupError(f"Project not found: {project_id}")
    return project


def _active_version_or_raise(db: Session, project: models.Project) -> models.Version:
    version = (
        db.execute(
            select(models.Version)
            .where(models.Version.project_id == project.project_id, models.Version.active.is_(True))
            .order_by(desc(models.Version.created_at))
        )
        .scalars()
        .first()
    )
    if version is None:
        raise LookupError(f"Active version not found for project {project.project_id}")
    return version
