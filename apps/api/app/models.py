from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.domain.enums import (
    AgentRunStatus,
    AgentTemplate,
    AssetType,
    ProjectStatus,
    TaskStatus,
    TranslationStatus,
)
from app.domain.ids import new_id


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("proj"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=ProjectStatus.DRAFT.value)
    source_language: Mapped[str] = mapped_column(String(16), nullable=False)
    target_languages: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    translation_style: Mapped[str] = mapped_column(String(128), nullable=False, default="short_drama_localized")
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    assets: Mapped[list["MediaAsset"]] = relationship(back_populates="project")
    segments: Mapped[list["Segment"]] = relationship(back_populates="project")
    speakers: Mapped[list["Speaker"]] = relationship(back_populates="project")
    tts_jobs: Mapped[list["TTSJob"]] = relationship(back_populates="project")
    agent_runs: Mapped[list["AgentRun"]] = relationship(back_populates="project")
    tasks: Mapped[list["Task"]] = relationship(back_populates="project")
    versions: Mapped[list["Version"]] = relationship(back_populates="project")


class Version(Base):
    __tablename__ = "versions"

    version_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ver"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False, default="default")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="versions")


class MediaAsset(Base):
    __tablename__ = "media_assets"

    asset_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("asset"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    language: Mapped[str | None] = mapped_column(String(16))
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str | None] = mapped_column(String(16))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(String(255))
    version_id: Mapped[str | None] = mapped_column(String(64), index=True)
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    project: Mapped[Project] = relationship(back_populates="assets")


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (UniqueConstraint("project_id", "index", name="uq_segments_project_index"),)

    segment_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("seg"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False, index=True)
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("speakers.speaker_id"))
    source_language: Mapped[str] = mapped_column(String(16), nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    asr_confidence: Mapped[float | None] = mapped_column(Float)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quality_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="segments")
    translations: Mapped[list["Translation"]] = relationship(back_populates="segment")
    tts_jobs: Mapped[list["TTSJob"]] = relationship(back_populates="segment")


class SegmentVersion(Base):
    __tablename__ = "segment_versions"

    segment_version_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("segver")
    )
    segment_id: Mapped[str] = mapped_column(ForeignKey("segments.segment_id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False, index=True)
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker_id: Mapped[str | None] = mapped_column(String(64))
    source_language: Mapped[str] = mapped_column(String(16), nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    asr_confidence: Mapped[float | None] = mapped_column(Float)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    quality_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    edited_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Translation(Base):
    __tablename__ = "translations"
    __table_args__ = (UniqueConstraint("translation_id", "target_language", name="uq_translation_language"),)

    translation_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("tr"))
    segment_id: Mapped[str] = mapped_column(ForeignKey("segments.segment_id"), nullable=False, index=True)
    target_language: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    style: Mapped[str] = mapped_column(String(128), nullable=False, default="short_drama_localized")
    model: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TranslationStatus.COMPLETED.value)
    edited_by: Mapped[str | None] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quality_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    segment: Mapped[Segment] = relationship(back_populates="translations")


class TranslationVersion(Base):
    __tablename__ = "translation_versions"

    translation_version_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("trver")
    )
    translation_id: Mapped[str] = mapped_column(ForeignKey("translations.translation_id"), nullable=False)
    segment_id: Mapped[str] = mapped_column(ForeignKey("segments.segment_id"), nullable=False, index=True)
    target_language: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    style: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    edited_by: Mapped[str | None] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Speaker(Base):
    __tablename__ = "speakers"

    speaker_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("spk"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_voice_sample_asset_id: Mapped[str | None] = mapped_column(String(64))
    target_voice_map: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)

    project: Mapped[Project] = relationship(back_populates="speakers")


class TTSJob(Base):
    __tablename__ = "tts_jobs"

    tts_job_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("tts"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False, index=True)
    segment_id: Mapped[str] = mapped_column(ForeignKey("segments.segment_id"), nullable=False, index=True)
    target_language: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    voice_id: Mapped[str | None] = mapped_column(String(128))
    target_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    speed: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TaskStatus.PENDING.value)
    output_asset_id: Mapped[str | None] = mapped_column(String(64))
    actual_duration_ms: Mapped[int | None] = mapped_column(Integer)
    provider: Mapped[str | None] = mapped_column(String(128))
    provider_task_id: Mapped[str | None] = mapped_column(String(128))
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    stale: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    quality_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="tts_jobs")
    segment: Mapped[Segment] = relationship(back_populates="tts_jobs")


class AgentRun(Base):
    __tablename__ = "agent_runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("run"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    template: Mapped[str] = mapped_column(String(32), nullable=False, default=AgentTemplate.SUBTITLE_DRAFT.value)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=AgentRunStatus.PENDING.value)
    current_step: Mapped[str | None] = mapped_column(String(128))
    source_language: Mapped[str] = mapped_column(String(16), nullable=False)
    target_languages: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    checkpoint: Mapped[str | None] = mapped_column(String(64))
    quality_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    run_context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="agent_runs")
    skill_runs: Mapped[list["SkillRun"]] = relationship(back_populates="agent_run")


class SkillRun(Base):
    __tablename__ = "skill_runs"

    skill_run_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("skillrun")
    )
    run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.run_id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False, index=True)
    skill_name: Mapped[str] = mapped_column(String(128), nullable=False)
    skill_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TaskStatus.PENDING.value)
    target_language: Mapped[str | None] = mapped_column(String(16), index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    input_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    output_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    provider: Mapped[str | None] = mapped_column(String(128))
    model: Mapped[str | None] = mapped_column(String(128))
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    quality_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    agent_run: Mapped[AgentRun] = relationship(back_populates="skill_runs")


class SkillDefinition(Base):
    __tablename__ = "skill_definitions"
    __table_args__ = (UniqueConstraint("skill_name", "skill_version", name="uq_skill_definition_version"),)

    skill_definition_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("skilldef")
    )
    skill_name: Mapped[str] = mapped_column(String(128), nullable=False)
    skill_version: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    default_provider: Mapped[str | None] = mapped_column(String(128))
    input_schema: Mapped[str] = mapped_column(String(128), nullable=False)
    output_schema: Mapped[str] = mapped_column(String(128), nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    retry_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class ManifestReference(Base):
    __tablename__ = "manifest_refs"
    __table_args__ = (UniqueConstraint("project_id", "version_id", name="uq_manifest_project_version"),)

    manifest_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: new_id("manifest")
    )
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    video_asset_id: Mapped[str | None] = mapped_column(String(64))
    subtitle_asset_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    audio_asset_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    download_asset_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class Task(Base):
    __tablename__ = "tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("task"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("agent_runs.run_id"), index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TaskStatus.PENDING.value)
    target_language: Mapped[str | None] = mapped_column(String(16), index=True)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    project: Mapped[Project] = relationship(back_populates="tasks")


class PackageRequest(Base):
    __tablename__ = "package_requests"

    package_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("pkg"))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    languages: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    include_intermediate_assets: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default=TaskStatus.PENDING.value)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("audit"))
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    run_id: Mapped[str | None] = mapped_column(String(64), index=True)
    segment_id: Mapped[str | None] = mapped_column(String(64), index=True)
    asset_id: Mapped[str | None] = mapped_column(String(64), index=True)
    request_path: Mapped[str | None] = mapped_column(String(512))
    method: Mapped[str | None] = mapped_column(String(16))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
