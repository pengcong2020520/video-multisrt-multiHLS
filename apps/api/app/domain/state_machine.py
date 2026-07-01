from __future__ import annotations

from app.domain.enums import AgentRunStatus, ProjectStatus, TaskStatus
from app.domain.errors import ApiError, ErrorCode


PROJECT_TRANSITIONS: dict[ProjectStatus, set[ProjectStatus]] = {
    ProjectStatus.DRAFT: {ProjectStatus.UPLOADED, ProjectStatus.PLANNING, ProjectStatus.FAILED, ProjectStatus.ARCHIVED},
    ProjectStatus.UPLOADED: {ProjectStatus.PLANNING, ProjectStatus.PROCESSING, ProjectStatus.FAILED, ProjectStatus.ARCHIVED},
    ProjectStatus.PLANNING: {ProjectStatus.PROCESSING, ProjectStatus.PROOFREADING, ProjectStatus.FAILED, ProjectStatus.ARCHIVED},
    ProjectStatus.PROCESSING: {ProjectStatus.PROOFREADING, ProjectStatus.GENERATING, ProjectStatus.COMPLETED, ProjectStatus.FAILED, ProjectStatus.ARCHIVED},
    ProjectStatus.PROOFREADING: {ProjectStatus.PROCESSING, ProjectStatus.GENERATING, ProjectStatus.FAILED, ProjectStatus.ARCHIVED},
    ProjectStatus.GENERATING: {ProjectStatus.COMPLETED, ProjectStatus.FAILED, ProjectStatus.ARCHIVED},
    ProjectStatus.COMPLETED: {ProjectStatus.PLANNING, ProjectStatus.GENERATING, ProjectStatus.ARCHIVED},
    ProjectStatus.FAILED: {ProjectStatus.PLANNING, ProjectStatus.PROCESSING, ProjectStatus.ARCHIVED},
    ProjectStatus.ARCHIVED: set(),
}

TASK_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.CANCELED},
    TaskStatus.RUNNING: {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELED, TaskStatus.RETRYING},
    TaskStatus.RETRYING: {TaskStatus.PENDING, TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.CANCELED},
    TaskStatus.SUCCEEDED: set(),
    TaskStatus.FAILED: {TaskStatus.RETRYING},
    TaskStatus.CANCELED: set(),
}

AGENT_RUN_TRANSITIONS: dict[AgentRunStatus, set[AgentRunStatus]] = {
    AgentRunStatus.PENDING: {AgentRunStatus.PLANNING, AgentRunStatus.RUNNING, AgentRunStatus.CANCELED, AgentRunStatus.FAILED},
    AgentRunStatus.PLANNING: {AgentRunStatus.RUNNING, AgentRunStatus.CANCELED, AgentRunStatus.FAILED},
    AgentRunStatus.RUNNING: {AgentRunStatus.WAITING_HUMAN, AgentRunStatus.SUCCEEDED, AgentRunStatus.CANCELED, AgentRunStatus.FAILED},
    AgentRunStatus.WAITING_HUMAN: {AgentRunStatus.RUNNING, AgentRunStatus.CANCELED, AgentRunStatus.FAILED},
    AgentRunStatus.SUCCEEDED: set(),
    AgentRunStatus.FAILED: set(),
    AgentRunStatus.CANCELED: set(),
}


def validate_project_transition(current: str, next_status: ProjectStatus | str) -> None:
    current_status = ProjectStatus(current)
    target_status = ProjectStatus(next_status)
    if target_status == current_status:
        return
    if target_status not in PROJECT_TRANSITIONS[current_status]:
        raise ApiError(
            ErrorCode.AGENT_RUN_FAILED,
            f"Invalid project status transition: {current_status} -> {target_status}",
        )


def validate_task_transition(current: str, next_status: TaskStatus | str) -> None:
    current_status = TaskStatus(current)
    target_status = TaskStatus(next_status)
    if target_status == current_status:
        return
    if target_status not in TASK_TRANSITIONS[current_status]:
        raise ApiError(
            ErrorCode.SKILL_RUN_FAILED,
            f"Invalid task status transition: {current_status} -> {target_status}",
        )


def validate_agent_run_transition(current: str, next_status: AgentRunStatus | str) -> None:
    current_status = AgentRunStatus(current)
    target_status = AgentRunStatus(next_status)
    if target_status == current_status:
        return
    if target_status not in AGENT_RUN_TRANSITIONS[current_status]:
        raise ApiError(
            ErrorCode.AGENT_RUN_FAILED,
            f"Invalid agent run status transition: {current_status} -> {target_status}",
        )


def require_waiting_human(status: str) -> None:
    if AgentRunStatus(status) != AgentRunStatus.WAITING_HUMAN:
        raise ApiError(
            ErrorCode.HUMAN_CHECKPOINT_REQUIRED,
            "Only waiting_human runs can be continued",
        )
