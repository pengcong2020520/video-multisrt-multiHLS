from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.orm import Session

from app import models
from app.domain.enums import AgentRunStatus, AgentTemplate, ProjectStatus, TaskStatus, TaskType
from app.domain.state_machine import validate_agent_run_transition, validate_project_transition
from app.queue import QueuePort


class AgentRuntimePort(Protocol):
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
        ...

    def continue_run(self, db: Session, run: models.AgentRun) -> models.AgentRun:
        ...


class InProcessAgentRuntime:
    def __init__(self, queue: QueuePort) -> None:
        self.queue = queue

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
        run = models.AgentRun(
            project_id=project.project_id,
            version_id=version.version_id,
            template=template.value,
            status=AgentRunStatus.PENDING.value,
            current_step=None,
            source_language=project.source_language,
            target_languages=target_languages,
            run_context=context,
            created_by=created_by,
        )
        db.add(run)
        db.flush()

        for task_type in task_plan_for_template(template, context):
            languages = target_languages if task_requires_language(task_type) else [None]
            for target_language in languages:
                db.add(
                    models.Task(
                        project_id=project.project_id,
                        run_id=run.run_id,
                        type=task_type.value,
                        status=TaskStatus.PENDING.value,
                        target_language=target_language,
                    )
                )

        self.queue.enqueue(
            "agent_runs",
            {
                "run_id": run.run_id,
                "project_id": project.project_id,
                "version_id": version.version_id,
                "template": template.value,
            },
        )
        return run

    def continue_run(self, db: Session, run: models.AgentRun) -> models.AgentRun:
        validate_agent_run_transition(run.status, AgentRunStatus.RUNNING)
        run.status = AgentRunStatus.RUNNING.value
        run.checkpoint = None
        run.current_step = "subtitle.generate"
        project = db.get(models.Project, run.project_id)
        if project:
            validate_project_transition(project.status, ProjectStatus.GENERATING)
            project.status = ProjectStatus.GENERATING.value
        self.queue.enqueue("agent_runs", {"run_id": run.run_id, "action": "continue"})
        return run


def task_requires_language(task_type: TaskType) -> bool:
    return task_type in {
        TaskType.TRANSLATE,
        TaskType.GENERATE_SUBTITLE,
        TaskType.TTS,
        TaskType.STITCH_TARGET_VOCAL,
        TaskType.MIX_AUDIO,
        TaskType.PACKAGE_OUTPUTS,
    }


def task_plan_for_template(template: AgentTemplate, context: dict[str, Any]) -> list[TaskType]:
    enable_source_separation = context.get("enable_source_separation", True)
    if template == AgentTemplate.PACKAGE_ONLY:
        return [TaskType.PACKAGE_OUTPUTS]
    if template == AgentTemplate.RERUN_SEGMENTS:
        return [
            TaskType.TTS,
            TaskType.STITCH_TARGET_VOCAL,
            TaskType.MIX_AUDIO,
            TaskType.PACKAGE_OUTPUTS,
        ]

    plan = [
        TaskType.PROBE_MEDIA,
        TaskType.EXTRACT_AUDIO,
    ]
    if enable_source_separation:
        plan.append(TaskType.SEPARATE_SOURCES)
    plan.extend(
        [
            TaskType.ASR,
            TaskType.SEGMENT_NORMALIZE,
            TaskType.TRANSLATE,
            TaskType.GENERATE_SUBTITLE,
        ]
    )
    if template == AgentTemplate.FULL_DUBBING or context.get("generate_tts"):
        plan.extend(
            [
                TaskType.TTS,
                TaskType.STITCH_TARGET_VOCAL,
                TaskType.MIX_AUDIO,
                TaskType.PACKAGE_OUTPUTS,
            ]
        )
    return plan
