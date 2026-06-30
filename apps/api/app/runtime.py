from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app import models
from app.domain.enums import AgentTemplate
from app.queue import QueuePort

_RUNTIME_SRC = Path(__file__).resolve().parents[3] / "packages" / "agent-runtime" / "src"
if _RUNTIME_SRC.exists() and str(_RUNTIME_SRC) not in sys.path:
    sys.path.append(str(_RUNTIME_SRC))

from agent_runtime import AgentRuntime, task_plan_for_template, task_requires_language  # noqa: E402
from agent_runtime.contracts import SkillRunnerPort  # noqa: E402
from agent_runtime.persister import ResponsePersisterPort  # noqa: E402
from agent_runtime.registry import SkillRegistry  # noqa: E402


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

    def rerun_language(
        self,
        db: Session,
        project_id: str,
        target_language: str,
        steps: list[str] | None = None,
        *,
        created_by: str | None = None,
    ) -> models.AgentRun:
        ...

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
        ...

    def get_run_status(self, db: Session, run_id: str) -> dict[str, Any]:
        ...


class InProcessAgentRuntime(AgentRuntime):
    def __init__(
        self,
        queue: QueuePort,
        *,
        skill_runner: SkillRunnerPort | None = None,
        registry: SkillRegistry | None = None,
        persister: ResponsePersisterPort | None = None,
    ) -> None:
        super().__init__(
            queue=queue,
            skill_runner=skill_runner,
            registry=registry,
            persister=persister,
            auto_execute=True,  # MVP: 同步执行，不需要独立 worker
        )


__all__ = [
    "AgentRuntimePort",
    "InProcessAgentRuntime",
    "task_plan_for_template",
    "task_requires_language",
]
