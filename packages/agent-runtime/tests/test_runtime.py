from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app import models
from app.db import Base
from app.domain.enums import AgentRunStatus, AgentTemplate, ProjectStatus, TaskStatus
from agent_runtime import AgentRuntime, SkillRequest, SkillResponse, SkillRegistry, template_step_names


ALL_SKILLS = {
    "media.probe",
    "media.extract_audio",
    "audio.separate_sources",
    "asr.transcribe",
    "asr.diarize",
    "transcript.normalize_segments",
    "localization.translate",
    "subtitle.generate",
    "voice.synthesize",
    "audio.stitch_vocals",
    "audio.mix",
    "package.manifest",
    "package.zip",
}


class ScriptedRunner:
    def __init__(self, scripts: dict[str, list[SkillResponse]] | None = None) -> None:
        self.scripts = scripts or {}
        self.calls: list[SkillRequest] = []
        self.counts: dict[str, int] = defaultdict(int)

    def invoke(self, request: SkillRequest) -> SkillResponse:
        self.calls.append(request)
        self.counts[request.skill_name] += 1
        scripted = self.scripts.get(request.skill_name)
        if scripted:
            return scripted.pop(0)
        language = request.input.get("target_language")
        outputs: dict[str, Any] = {
            "output_refs": [f"{request.skill_name}:{language or 'all'}:{self.counts[request.skill_name]}"]
        }
        if request.skill_name == "transcript.normalize_segments":
            outputs["segments_version"] = "segver_runtime_001"
        if request.skill_name == "localization.translate" and language:
            outputs["translation_version"] = f"trver_{language}_001"
        return SkillResponse.succeeded(
            outputs,
            usage={"provider": request.config.get("provider"), "model": f"{request.skill_name}:model"},
        )


@pytest.fixture()
def db_session(tmp_path) -> Iterable[Session]:
    engine = create_engine(
        f"sqlite:///{tmp_path}/runtime-test.sqlite3",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    with factory() as session:
        yield session


def test_template_step_order_is_fixed() -> None:
    assert template_step_names(AgentTemplate.SUBTITLE_DRAFT) == [
        "media.probe",
        "media.extract_audio",
        "audio.separate_sources",
        "asr.transcribe",
        "transcript.normalize_segments",
        "localization.translate",
        "subtitle.generate",
        "pause_for_proofreading",
    ]
    assert template_step_names(AgentTemplate.FULL_DUBBING) == [
        "media.probe",
        "media.extract_audio",
        "audio.separate_sources",
        "asr.transcribe",
        "asr.diarize",
        "transcript.normalize_segments",
        "localization.translate",
        "pause_for_proofreading",
        "subtitle.generate",
        "voice.synthesize",
        "audio.stitch_vocals",
        "audio.mix",
        "package.manifest",
        "package.zip",
    ]
    assert template_step_names(AgentTemplate.RERUN_SEGMENTS) == [
        "voice.synthesize",
        "audio.stitch_vocals",
        "audio.mix",
        "package.manifest",
    ]
    assert template_step_names(AgentTemplate.PACKAGE_ONLY) == ["package.manifest", "package.zip"]


def test_checkpoint_pause_and_resume(db_session: Session) -> None:
    project, version = seed_project(db_session, status=ProjectStatus.PLANNING, target_languages=["en-US"])
    seed_skill_definitions(db_session)
    db_session.commit()

    runtime = AgentRuntime(
        skill_runner=ScriptedRunner(),
        registry=SkillRegistry(),
        auto_execute=True,
    )
    run = runtime.create_run(
        db_session,
        project,
        version=version,
        template=AgentTemplate.FULL_DUBBING,
        created_by="user_001",
        target_languages=project.target_languages,
        context={},
    )

    assert run.status == AgentRunStatus.WAITING_HUMAN.value
    assert run.checkpoint == "proofreading"
    assert run.current_step == "pause_for_proofreading"
    assert db_session.get(models.Project, project.project_id).status == ProjectStatus.PROOFREADING.value
    assert [skill.skill_name for skill in skill_runs(db_session, run)] == [
        "media.probe",
        "media.extract_audio",
        "audio.separate_sources",
        "asr.transcribe",
        "asr.diarize",
        "transcript.normalize_segments",
        "localization.translate",
    ]

    resumed = runtime.continue_run(db_session, run)

    assert resumed.status == AgentRunStatus.SUCCEEDED.value
    assert resumed.checkpoint is None
    assert db_session.get(models.Project, project.project_id).status == ProjectStatus.COMPLETED.value
    assert [skill.skill_name for skill in skill_runs(db_session, run)][-6:] == [
        "subtitle.generate",
        "voice.synthesize",
        "audio.stitch_vocals",
        "audio.mix",
        "package.manifest",
        "package.zip",
    ]
    assert resumed.run_context["human_checkpoints"] == ["proofreading"]


def test_skill_run_records_and_retry_appends_history(db_session: Session) -> None:
    project, version = seed_project(db_session, status=ProjectStatus.PLANNING, target_languages=["en-US"])
    seed_skill_definitions(db_session, retry_overrides={"localization.translate": 1})
    db_session.commit()
    runner = ScriptedRunner(
        {
            "localization.translate": [
                SkillResponse.failed("TRANSLATION_FAILED", "Provider request failed"),
                SkillResponse.succeeded(
                    {"translation_version": "trver_retry_001"},
                    usage={"provider": "deepseek", "model": "deepseek-default"},
                ),
            ]
        }
    )
    runtime = AgentRuntime(skill_runner=runner, registry=SkillRegistry(), auto_execute=True)

    run = runtime.create_run(
        db_session,
        project,
        version=version,
        template=AgentTemplate.SUBTITLE_DRAFT,
        created_by="user_001",
        target_languages=["en-US"],
        context={},
    )

    translate_runs = [
        skill_run for skill_run in skill_runs(db_session, run) if skill_run.skill_name == "localization.translate"
    ]
    assert [skill_run.status for skill_run in translate_runs] == [
        TaskStatus.FAILED.value,
        TaskStatus.SUCCEEDED.value,
    ]
    assert translate_runs[0].error == {
        "code": "TRANSLATION_FAILED",
        "message": "Provider request failed",
    }
    assert translate_runs[1].provider == "deepseek"
    assert translate_runs[1].model == "deepseek-default"
    assert translate_runs[1].output_refs == ["trver_retry_001"]
    assert translate_runs[0].skill_run_id != translate_runs[1].skill_run_id
    assert run.status == AgentRunStatus.WAITING_HUMAN.value


def test_rerun_segments_passes_selected_segments_without_checkpoint(db_session: Session) -> None:
    project, version = seed_project(db_session, status=ProjectStatus.COMPLETED, target_languages=["en-US"])
    segment = models.Segment(
        project_id=project.project_id,
        index=1,
        start_ms=1000,
        end_ms=2500,
        source_language="zh-CN",
        source_text="Rerun this line",
        locked=True,
        quality_flags=[],
    )
    db_session.add(segment)
    seed_skill_definitions(db_session)
    db_session.commit()
    runner = ScriptedRunner()
    runtime = AgentRuntime(skill_runner=runner, registry=SkillRegistry(), auto_execute=True)

    run = runtime.rerunSegments(
        db_session,
        project.project_id,
        "en-US",
        [segment.segment_id],
        ["tts", "mix"],
    )

    assert run.template == AgentTemplate.RERUN_SEGMENTS.value
    assert run.status == AgentRunStatus.SUCCEEDED.value
    assert run.checkpoint is None
    assert [request.skill_name for request in runner.calls] == [
        "voice.synthesize",
        "audio.stitch_vocals",
        "audio.mix",
        "package.manifest",
    ]
    assert runner.calls[0].input["selected_segment_ids"] == [segment.segment_id]
    assert db_session.get(models.Project, project.project_id).status == ProjectStatus.COMPLETED.value


def test_locked_segment_anti_overwrite_fails_skill_run(db_session: Session) -> None:
    project, version = seed_project(db_session, status=ProjectStatus.PLANNING, target_languages=["en-US"])
    locked_segment = models.Segment(
        project_id=project.project_id,
        index=1,
        start_ms=1000,
        end_ms=2000,
        source_language="zh-CN",
        source_text="Locked source",
        locked=True,
        quality_flags=[],
    )
    db_session.add(locked_segment)
    seed_skill_definitions(db_session)
    db_session.commit()
    runner = ScriptedRunner(
        {
            "transcript.normalize_segments": [
                SkillResponse.succeeded(
                    {
                        "segments_version": "segver_bad",
                        "updated_segment_ids": [locked_segment.segment_id],
                    }
                )
            ]
        }
    )
    runtime = AgentRuntime(skill_runner=runner, registry=SkillRegistry(), auto_execute=True)

    run = runtime.create_run(
        db_session,
        project,
        version=version,
        template=AgentTemplate.SUBTITLE_DRAFT,
        created_by="user_001",
        target_languages=["en-US"],
        context={},
    )

    assert run.status == AgentRunStatus.FAILED.value
    normalize_run = [
        skill_run
        for skill_run in skill_runs(db_session, run)
        if skill_run.skill_name == "transcript.normalize_segments"
    ][0]
    assert normalize_run.status == TaskStatus.FAILED.value
    assert normalize_run.error == {
        "code": "INVALID_REQUEST",
        "message": "Skill response attempted to overwrite locked segment",
    }
    db_session.refresh(locked_segment)
    assert locked_segment.source_text == "Locked source"
    assert "localization.translate" not in [request.skill_name for request in runner.calls]


def seed_project(
    db: Session,
    *,
    status: ProjectStatus,
    target_languages: list[str],
) -> tuple[models.Project, models.Version]:
    project = models.Project(
        name="episode_01",
        status=status.value,
        source_language="zh-CN",
        target_languages=target_languages,
        created_by="user_001",
    )
    db.add(project)
    db.flush()
    version = models.Version(project_id=project.project_id, label="v1", created_by="user_001")
    db.add(version)
    db.flush()
    return project, version


def seed_skill_definitions(
    db: Session,
    retry_overrides: dict[str, int] | None = None,
) -> None:
    retry_overrides = retry_overrides or {}
    for skill_name in ALL_SKILLS:
        db.add(
            models.SkillDefinition(
                skill_name=skill_name,
                skill_version="1.0.0",
                enabled=True,
                default_provider=provider_for(skill_name),
                input_schema=f"{schema_prefix(skill_name)}Input",
                output_schema=f"{schema_prefix(skill_name)}Output",
                timeout_seconds=120,
                retry_limit=retry_overrides.get(skill_name, 0),
            )
        )
    db.flush()


def skill_runs(db: Session, run: models.AgentRun) -> list[models.SkillRun]:
    return list(
        db.execute(
            select(models.SkillRun)
            .where(models.SkillRun.run_id == run.run_id)
            .order_by(models.SkillRun.started_at, models.SkillRun.skill_run_id)
        )
        .scalars()
        .all()
    )


def provider_for(skill_name: str) -> str:
    if skill_name.startswith("localization."):
        return "deepseek"
    if skill_name.startswith("voice."):
        return "minimax"
    return "internal"


def schema_prefix(skill_name: str) -> str:
    return "".join(part.capitalize() for token in skill_name.split(".") for part in token.split("_"))
