from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import (
    AgentRunStatus,
    AgentTemplate,
    GenerateScope,
    GenerateStep,
    ProjectStatus,
    SOURCE_LANGUAGES,
    TARGET_LANGUAGES,
)


class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateProjectRequest(StrictRequest):
    name: str = Field(min_length=1, max_length=255)
    source_language: str
    target_languages: list[str] = Field(default_factory=list)
    translation_style: str = Field(default="short_drama_localized", min_length=1, max_length=128)

    @field_validator("source_language")
    @classmethod
    def validate_source_language(cls, value: str) -> str:
        if value not in SOURCE_LANGUAGES:
            raise ValueError(f"source_language must be one of {sorted(SOURCE_LANGUAGES)}")
        return value

    @field_validator("target_languages")
    @classmethod
    def validate_target_languages(cls, values: list[str]) -> list[str]:
        unique = list(dict.fromkeys(values))
        unsupported = [value for value in unique if value not in TARGET_LANGUAGES]
        if unsupported:
            raise ValueError(f"unsupported target_languages: {unsupported}")
        return unique


class CreateProjectResponse(BaseModel):
    project_id: str
    upload_url: str
    preview_url: str


class ProcessProjectRequest(StrictRequest):
    enable_source_separation: bool = True
    enable_diarization: bool = True
    generate_tts: bool = False
    generate_preview_mp4: bool = False
    agent_template: AgentTemplate = AgentTemplate.SUBTITLE_DRAFT


class RunResponse(BaseModel):
    run_id: str
    status: AgentRunStatus


class OnDemandLanguageRequest(StrictRequest):
    target_language: str

    @field_validator("target_language")
    @classmethod
    def validate_target_language(cls, value: str) -> str:
        if value not in TARGET_LANGUAGES:
            raise ValueError(f"unsupported target_language: {value}")
        return value


class ContinueRunRequest(StrictRequest):
    checkpoint: str
    confirmed: bool


class ProjectEntity(BaseModel):
    project_id: str
    name: str
    status: ProjectStatus | str
    source_language: str
    target_languages: list[str]
    duration_ms: int | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class MediaAssetEntity(BaseModel):
    asset_id: str
    project_id: str
    type: str
    language: str | None
    uri: str
    format: str | None
    duration_ms: int | None
    size_bytes: int | None
    checksum: str | None
    created_at: datetime


class SegmentEntity(BaseModel):
    segment_id: str
    project_id: str
    index: int
    start_ms: int
    end_ms: int
    speaker_id: str | None
    source_language: str
    source_text: str
    asr_confidence: float | None
    locked: bool
    quality_flags: list[str]


class TranslationEntity(BaseModel):
    translation_id: str
    segment_id: str
    target_language: str
    text: str
    style: str
    model: str | None
    prompt_version: str | None
    status: str
    edited_by: str | None
    updated_at: datetime


class TTSJobEntity(BaseModel):
    tts_job_id: str
    project_id: str
    segment_id: str
    target_language: str
    text: str
    voice_id: str | None
    target_duration_ms: int
    speed: float
    status: str
    output_asset_id: str | None
    actual_duration_ms: int | None
    provider: str | None
    provider_task_id: str | None
    error: dict[str, Any] | None


class AgentRunEntity(BaseModel):
    run_id: str
    project_id: str
    version_id: str
    template: str
    status: str
    current_step: str | None
    source_language: str
    target_languages: list[str]
    created_by: str
    created_at: datetime
    updated_at: datetime


class SkillRunEntity(BaseModel):
    skill_run_id: str
    run_id: str
    project_id: str
    skill_name: str
    skill_version: str
    status: str
    target_language: str | None
    started_at: datetime | None
    finished_at: datetime | None
    input_refs: list[str]
    output_refs: list[str]
    provider: str | None
    model: str | None
    error: dict[str, Any] | None


class TaskEntity(BaseModel):
    task_id: str
    project_id: str
    run_id: str | None
    type: str
    status: str
    target_language: str | None
    error_code: str | None
    error_message: str | None
    retry_count: int
    created_at: datetime
    updated_at: datetime


class QueryAgentRunResponse(BaseModel):
    agent_run: AgentRunEntity
    skill_runs: list[SkillRunEntity]
    current_checkpoint: str | None
    quality_flags: list[str]


class QueryProjectResponse(BaseModel):
    project: ProjectEntity
    tasks: list[TaskEntity]
    assets: list[MediaAssetEntity]
    languages: list[str]


class SegmentBundle(BaseModel):
    segment: SegmentEntity
    translation: TranslationEntity | None
    tts_job: TTSJobEntity | None


class QuerySegmentsResponse(BaseModel):
    segments: list[SegmentBundle]


class PatchSegmentRequest(StrictRequest):
    start_ms: int | None = None
    end_ms: int | None = None
    speaker_id: str | None = None
    source_text: str | None = None
    translations: dict[str, str] | None = None
    locked: bool | None = None

    @field_validator("translations")
    @classmethod
    def validate_translations(cls, values: dict[str, str] | None) -> dict[str, str] | None:
        if values is None:
            return values
        unsupported = [language for language in values if language not in TARGET_LANGUAGES]
        if unsupported:
            raise ValueError(f"unsupported translation languages: {unsupported}")
        return values


class GenerateProjectRequest(StrictRequest):
    target_language: str
    scope: GenerateScope
    steps: list[GenerateStep] = Field(default_factory=list)
    segment_ids: list[str] = Field(default_factory=list)
    agent_template: AgentTemplate = AgentTemplate.FULL_DUBBING

    @field_validator("target_language")
    @classmethod
    def validate_target_language(cls, value: str) -> str:
        if value not in TARGET_LANGUAGES:
            raise ValueError(f"unsupported target_language: {value}")
        return value


class ManifestVideo(BaseModel):
    url: str
    duration_ms: int | None


class ManifestSubtitle(BaseModel):
    language: str
    label: str
    format: str
    url: str


class ManifestAudioTrack(BaseModel):
    language: str
    label: str
    url: str


class ManifestDownload(BaseModel):
    type: str
    label: str
    url: str


class ManifestResponse(BaseModel):
    project_id: str
    version_id: str
    video: ManifestVideo
    subtitles: list[ManifestSubtitle]
    audio_tracks: list[ManifestAudioTrack]
    downloads: list[ManifestDownload]


class PackageRequestBody(StrictRequest):
    version_id: str
    languages: list[str] = Field(min_length=1)
    include_intermediate_assets: bool = False

    @field_validator("languages")
    @classmethod
    def validate_languages(cls, values: list[str]) -> list[str]:
        unique = list(dict.fromkeys(values))
        unsupported = [value for value in unique if value not in TARGET_LANGUAGES]
        if unsupported:
            raise ValueError(f"unsupported package languages: {unsupported}")
        return unique


class PackageResponse(BaseModel):
    package_id: str
    status: str
