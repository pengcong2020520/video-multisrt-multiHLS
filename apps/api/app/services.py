from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app import models
from app.domain.enums import (
    AgentRunStatus,
    AgentTemplate,
    AssetType,
    GenerateScope,
    ProjectStatus,
    TARGET_LANGUAGES,
    TaskStatus,
    TaskType,
    TranslationStatus,
)
from app.domain.errors import ApiError, ErrorCode
from app.domain.file_paths import private_uri, storage_key_for_asset
from app.domain.state_machine import (
    require_waiting_human,
    validate_agent_run_transition,
    validate_project_transition,
)
from app.runtime import AgentRuntimePort
from app.schemas import (
    ContinueRunRequest,
    CreateProjectRequest,
    GenerateProjectRequest,
    PackageRequestBody,
    PatchSegmentRequest,
    ProcessProjectRequest,
)
from app.serializers import (
    agent_run_to_dict,
    asset_to_dict,
    project_to_dict,
    segment_to_dict,
    skill_run_to_dict,
    task_to_dict,
    translation_to_dict,
    tts_job_to_dict,
)
from app.storage import ObjectStoragePort
from app.queue import QueuePort


def create_project(
    db: Session,
    storage: ObjectStoragePort,
    payload: CreateProjectRequest,
    *,
    actor_id: str,
) -> tuple[models.Project, str]:
    project = models.Project(
        name=payload.name,
        status=ProjectStatus.DRAFT.value,
        source_language=payload.source_language,
        target_languages=payload.target_languages,
        translation_style=payload.translation_style,
        created_by=actor_id,
    )
    db.add(project)
    db.flush()

    version = models.Version(project_id=project.project_id, label="initial", created_by=actor_id)
    db.add(version)

    source_key = storage_key_for_asset(project.project_id, AssetType.SOURCE_VIDEO)
    source_asset = models.MediaAsset(
        project_id=project.project_id,
        type=AssetType.SOURCE_VIDEO.value,
        language=None,
        uri=private_uri(source_key),
        format="mp4",
    )
    db.add(source_asset)
    upload_url = storage.generate_upload_url(source_key)
    return project, upload_url


def submit_processing(
    db: Session,
    runtime: AgentRuntimePort,
    project_id: str,
    payload: ProcessProjectRequest,
    *,
    actor_id: str,
) -> models.AgentRun:
    project = get_project_or_404(db, project_id)
    _set_project_status(project, ProjectStatus.PLANNING)
    version = get_or_create_active_version(db, project, actor_id=actor_id)
    context = payload.model_dump(mode="json")
    run = runtime.create_run(
        db,
        project,
        version=version,
        template=payload.agent_template,
        created_by=actor_id,
        target_languages=project.target_languages,
        context=context,
    )
    return run


def query_agent_run(db: Session, run_id: str) -> dict[str, Any]:
    run = get_run_or_404(db, run_id)
    skill_runs = (
        db.execute(
            select(models.SkillRun)
            .where(models.SkillRun.run_id == run.run_id)
            .order_by(models.SkillRun.started_at, models.SkillRun.skill_run_id)
        )
        .scalars()
        .all()
    )
    checkpoint = run.checkpoint
    if run.status == AgentRunStatus.WAITING_HUMAN.value and checkpoint is None:
        checkpoint = "proofreading"
    return {
        "agent_run": agent_run_to_dict(run),
        "skill_runs": [skill_run_to_dict(skill_run) for skill_run in skill_runs],
        "current_checkpoint": checkpoint,
        "quality_flags": run.quality_flags,
    }


def continue_agent_run(
    db: Session,
    runtime: AgentRuntimePort,
    run_id: str,
    payload: ContinueRunRequest,
) -> models.AgentRun:
    run = get_run_or_404(db, run_id)
    require_waiting_human(run.status)
    expected_checkpoint = run.checkpoint or "proofreading"
    if payload.checkpoint != expected_checkpoint:
        raise ApiError(
            ErrorCode.HUMAN_CHECKPOINT_REQUIRED,
            f"Expected checkpoint {expected_checkpoint}",
        )
    if not payload.confirmed:
        raise ApiError(ErrorCode.HUMAN_CHECKPOINT_REQUIRED, "Human checkpoint is not confirmed")
    if not _has_saved_human_edit(db, run):
        raise ApiError(
            ErrorCode.HUMAN_CHECKPOINT_REQUIRED,
            "Save user segment or translation edits before continuing the run",
        )
    return runtime.continue_run(db, run)


def query_project(db: Session, project_id: str) -> dict[str, Any]:
    project = get_project_or_404(db, project_id)
    tasks = (
        db.execute(
            select(models.Task)
            .where(models.Task.project_id == project.project_id)
            .order_by(models.Task.created_at, models.Task.task_id)
        )
        .scalars()
        .all()
    )
    assets = (
        db.execute(
            select(models.MediaAsset)
            .where(models.MediaAsset.project_id == project.project_id)
            .order_by(models.MediaAsset.created_at, models.MediaAsset.asset_id)
        )
        .scalars()
        .all()
    )
    return {
        "project": project_to_dict(project),
        "tasks": [task_to_dict(task) for task in tasks],
        "assets": [asset_to_dict(asset) for asset in assets],
        "languages": project.target_languages,
    }


def query_segments(
    db: Session, project_id: str, target_language: str | None
) -> dict[str, list[dict[str, Any]]]:
    project = get_project_or_404(db, project_id)
    if target_language is not None and target_language not in TARGET_LANGUAGES:
        raise ApiError(ErrorCode.INVALID_REQUEST, f"unsupported target_language: {target_language}")
    segments = (
        db.execute(
            select(models.Segment)
            .where(models.Segment.project_id == project.project_id)
            .order_by(models.Segment.index)
        )
        .scalars()
        .all()
    )
    bundles = []
    for segment in segments:
        translation = _active_translation(db, segment.segment_id, target_language) if target_language else None
        tts_job = _latest_tts_job(db, segment.segment_id, target_language) if target_language else None
        bundles.append(
            {
                "segment": segment_to_dict(segment),
                "translation": translation_to_dict(translation),
                "tts_job": tts_job_to_dict(tts_job),
            }
        )
    return {"segments": bundles}


def update_segment(
    db: Session,
    project_id: str,
    segment_id: str,
    payload: PatchSegmentRequest,
    *,
    actor_id: str,
) -> dict[str, Any]:
    project = get_project_or_404(db, project_id)
    segment = get_segment_or_404(db, project.project_id, segment_id)
    changed_fields = payload.model_dump(exclude_unset=True)
    if not changed_fields:
        raise ApiError(ErrorCode.INVALID_REQUEST, "At least one segment field must be provided")

    new_start_ms = payload.start_ms if "start_ms" in payload.model_fields_set else segment.start_ms
    new_end_ms = payload.end_ms if "end_ms" in payload.model_fields_set else segment.end_ms
    if new_start_ms is None or new_end_ms is None:
        raise ApiError(ErrorCode.INVALID_REQUEST, "start_ms and end_ms cannot be null")
    if new_start_ms >= new_end_ms:
        raise ApiError(ErrorCode.INVALID_REQUEST, "segment start_ms must be less than end_ms")

    timeline_changed = (
        "start_ms" in payload.model_fields_set or "end_ms" in payload.model_fields_set
    )
    if "start_ms" in payload.model_fields_set:
        segment.start_ms = payload.start_ms  # type: ignore[assignment]
    if "end_ms" in payload.model_fields_set:
        segment.end_ms = payload.end_ms  # type: ignore[assignment]
    if "speaker_id" in payload.model_fields_set:
        segment.speaker_id = payload.speaker_id
    if "source_text" in payload.model_fields_set:
        segment.source_text = payload.source_text or ""
    if "locked" in payload.model_fields_set:
        segment.locked = bool(payload.locked)

    db.add(
        models.SegmentVersion(
            segment_id=segment.segment_id,
            project_id=segment.project_id,
            index=segment.index,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            speaker_id=segment.speaker_id,
            source_language=segment.source_language,
            source_text=segment.source_text,
            asr_confidence=segment.asr_confidence,
            locked=segment.locked,
            quality_flags=segment.quality_flags,
            edited_by=actor_id,
        )
    )

    changed_languages: list[str] = []
    for language, text in (payload.translations or {}).items():
        changed_languages.append(language)
        _replace_active_translation(db, project, segment, language, text, actor_id)

    stale_languages = changed_languages or project.target_languages
    if timeline_changed or changed_languages:
        _mark_downstream_stale(db, project.project_id, segment.segment_id, stale_languages)

    preferred_language = changed_languages[0] if changed_languages else None
    translation = (
        _active_translation(db, segment.segment_id, preferred_language)
        if preferred_language
        else None
    )
    tts_job = (
        _latest_tts_job(db, segment.segment_id, preferred_language)
        if preferred_language
        else None
    )
    return {
        "segment": segment_to_dict(segment),
        "translation": translation_to_dict(translation),
        "tts_job": tts_job_to_dict(tts_job),
    }


def generate_project(
    db: Session,
    runtime: AgentRuntimePort,
    project_id: str,
    payload: GenerateProjectRequest,
    *,
    actor_id: str,
) -> models.AgentRun:
    project = get_project_or_404(db, project_id)
    if payload.scope == GenerateScope.SEGMENTS and not payload.segment_ids:
        raise ApiError(ErrorCode.INVALID_REQUEST, "segment_ids are required for segments scope")
    if payload.scope == GenerateScope.PACKAGE and payload.agent_template != AgentTemplate.PACKAGE_ONLY:
        raise ApiError(ErrorCode.INVALID_REQUEST, "package scope requires package_only agent_template")
    if payload.scope == GenerateScope.SEGMENTS and payload.agent_template != AgentTemplate.RERUN_SEGMENTS:
        raise ApiError(ErrorCode.INVALID_REQUEST, "segments scope requires rerun_segments agent_template")

    _set_project_status(project, ProjectStatus.GENERATING)
    version = get_or_create_active_version(db, project, actor_id=actor_id)
    context = payload.model_dump(mode="json")
    return runtime.create_run(
        db,
        project,
        version=version,
        template=payload.agent_template,
        created_by=actor_id,
        target_languages=[payload.target_language],
        context=context,
    )


def get_manifest(
    db: Session,
    storage: ObjectStoragePort,
    project_id: str,
    version_id: str | None,
) -> dict[str, Any]:
    project = get_project_or_404(db, project_id)
    version = get_version_or_active(db, project, version_id)
    source_video = _latest_asset(db, project.project_id, AssetType.SOURCE_VIDEO)
    if source_video is None:
        raise ApiError(ErrorCode.INVALID_VIDEO, "Project source video is missing")

    subtitles = []
    for asset in _assets_by_types(db, project.project_id, {AssetType.SUBTITLE_VTT}):
        if asset.stale:
            continue
        subtitles.append(
            {
                "language": asset.language or project.source_language,
                "label": language_label(asset.language or project.source_language),
                "format": "vtt",
                "url": storage.generate_download_url(asset.uri),
            }
        )

    audio_tracks = []
    for asset in _assets_by_types(
        db, project.project_id, {AssetType.SOURCE_AUDIO, AssetType.TARGET_MIX_AUDIO}
    ):
        if asset.stale:
            continue
        if asset.type == AssetType.SOURCE_AUDIO.value:
            language = "source"
            label = "原音轨"
        else:
            language = asset.language or ""
            label = f"{language_label(language)} Dub"
        audio_tracks.append(
            {
                "language": language,
                "label": label,
                "url": storage.generate_download_url(asset.uri),
            }
        )

    downloads = []
    for asset in _assets_by_types(db, project.project_id, {AssetType.PACKAGE_ZIP}):
        if asset.stale:
            continue
        downloads.append(
            {
                "type": AssetType.PACKAGE_ZIP.value,
                "label": "完整结果包",
                "url": storage.generate_download_url(asset.uri),
            }
        )

    return {
        "project_id": project.project_id,
        "version_id": version.version_id,
        "video": {
            "url": storage.generate_download_url(source_video.uri),
            "duration_ms": source_video.duration_ms or project.duration_ms,
        },
        "subtitles": subtitles,
        "audio_tracks": audio_tracks,
        "downloads": downloads,
    }


def request_package(
    db: Session,
    queue: QueuePort,
    project_id: str,
    payload: PackageRequestBody,
    *,
    actor_id: str,
) -> models.PackageRequest:
    project = get_project_or_404(db, project_id)
    version = get_version_or_active(db, project, payload.version_id)
    package = models.PackageRequest(
        project_id=project.project_id,
        version_id=version.version_id,
        languages=payload.languages,
        include_intermediate_assets=payload.include_intermediate_assets,
        status=TaskStatus.PENDING.value,
        created_by=actor_id,
    )
    db.add(package)
    db.flush()
    db.add(
        models.Task(
            project_id=project.project_id,
            run_id=None,
            type=TaskType.PACKAGE_OUTPUTS.value,
            status=TaskStatus.PENDING.value,
        )
    )
    queue.enqueue(
        "package_outputs",
        {
            "package_id": package.package_id,
            "project_id": project.project_id,
            "version_id": version.version_id,
            "languages": payload.languages,
            "include_intermediate_assets": payload.include_intermediate_assets,
        },
    )
    return package


def get_project_or_404(db: Session, project_id: str) -> models.Project:
    project = db.get(models.Project, project_id)
    if project is None:
        raise ApiError(ErrorCode.NOT_FOUND, "Project not found", status_code=404)
    return project


def get_run_or_404(db: Session, run_id: str) -> models.AgentRun:
    run = db.get(models.AgentRun, run_id)
    if run is None:
        raise ApiError(ErrorCode.NOT_FOUND, "Agent run not found", status_code=404)
    return run


def get_segment_or_404(db: Session, project_id: str, segment_id: str) -> models.Segment:
    segment = db.get(models.Segment, segment_id)
    if segment is None or segment.project_id != project_id:
        raise ApiError(ErrorCode.NOT_FOUND, "Segment not found", status_code=404)
    return segment


def get_or_create_active_version(
    db: Session, project: models.Project, *, actor_id: str
) -> models.Version:
    version = (
        db.execute(
            select(models.Version)
            .where(models.Version.project_id == project.project_id, models.Version.active.is_(True))
            .order_by(desc(models.Version.created_at))
        )
        .scalars()
        .first()
    )
    if version is not None:
        return version
    version = models.Version(project_id=project.project_id, label="default", created_by=actor_id)
    db.add(version)
    db.flush()
    return version


def get_version_or_active(
    db: Session, project: models.Project, version_id: str | None
) -> models.Version:
    if version_id:
        version = db.get(models.Version, version_id)
        if version is None or version.project_id != project.project_id:
            raise ApiError(ErrorCode.NOT_FOUND, "Version not found", status_code=404)
        return version
    return get_or_create_active_version(db, project, actor_id=project.created_by)


def _set_project_status(project: models.Project, status: ProjectStatus) -> None:
    validate_project_transition(project.status, status)
    project.status = status.value


def _has_saved_human_edit(db: Session, run: models.AgentRun) -> bool:
    audit = (
        db.execute(
            select(models.AuditLog.audit_id)
            .where(
                models.AuditLog.project_id == run.project_id,
                models.AuditLog.action == "segment.update",
                models.AuditLog.created_at >= run.created_at,
            )
            .limit(1)
        )
        .scalars()
        .first()
    )
    return audit is not None


def _active_translation(
    db: Session, segment_id: str, target_language: str | None
) -> models.Translation | None:
    if target_language is None:
        return None
    return (
        db.execute(
            select(models.Translation)
            .where(
                models.Translation.segment_id == segment_id,
                models.Translation.target_language == target_language,
                models.Translation.active.is_(True),
            )
            .order_by(desc(models.Translation.updated_at))
        )
        .scalars()
        .first()
    )


def _latest_tts_job(
    db: Session, segment_id: str, target_language: str | None
) -> models.TTSJob | None:
    if target_language is None:
        return None
    return (
        db.execute(
            select(models.TTSJob)
            .where(
                models.TTSJob.segment_id == segment_id,
                models.TTSJob.target_language == target_language,
            )
            .order_by(desc(models.TTSJob.updated_at))
        )
        .scalars()
        .first()
    )


def _replace_active_translation(
    db: Session,
    project: models.Project,
    segment: models.Segment,
    target_language: str,
    text: str,
    actor_id: str,
) -> models.Translation:
    previous = _active_translation(db, segment.segment_id, target_language)
    if previous is not None:
        previous.active = False
    translation = models.Translation(
        segment_id=segment.segment_id,
        target_language=target_language,
        text=text,
        style=previous.style if previous else project.translation_style,
        model=previous.model if previous else None,
        prompt_version=previous.prompt_version if previous else None,
        status=TranslationStatus.COMPLETED.value,
        edited_by=actor_id,
        active=True,
        stale=False,
    )
    db.add(translation)
    db.flush()
    db.add(
        models.TranslationVersion(
            translation_id=translation.translation_id,
            segment_id=segment.segment_id,
            target_language=target_language,
            text=translation.text,
            style=translation.style,
            model=translation.model,
            prompt_version=translation.prompt_version,
            status=translation.status,
            edited_by=translation.edited_by,
            active=True,
        )
    )
    return translation


def _mark_downstream_stale(
    db: Session, project_id: str, segment_id: str, languages: list[str]
) -> None:
    tts_jobs = (
        db.execute(
            select(models.TTSJob).where(
                models.TTSJob.project_id == project_id,
                models.TTSJob.segment_id == segment_id,
                models.TTSJob.target_language.in_(languages),
            )
        )
        .scalars()
        .all()
    )
    for tts_job in tts_jobs:
        tts_job.stale = True

    stale_asset_types = {
        AssetType.SUBTITLE_SRT.value,
        AssetType.SUBTITLE_VTT.value,
        AssetType.TARGET_VOCAL.value,
        AssetType.TARGET_MIX_AUDIO.value,
        AssetType.PREVIEW_VIDEO.value,
        AssetType.PACKAGE_ZIP.value,
    }
    assets = (
        db.execute(
            select(models.MediaAsset).where(
                models.MediaAsset.project_id == project_id,
                models.MediaAsset.type.in_(stale_asset_types),
            )
        )
        .scalars()
        .all()
    )
    for asset in assets:
        if asset.type == AssetType.PACKAGE_ZIP.value or asset.language in languages:
            asset.stale = True


def _latest_asset(
    db: Session, project_id: str, asset_type: AssetType
) -> models.MediaAsset | None:
    return (
        db.execute(
            select(models.MediaAsset)
            .where(
                models.MediaAsset.project_id == project_id,
                models.MediaAsset.type == asset_type.value,
            )
            .order_by(desc(models.MediaAsset.created_at))
        )
        .scalars()
        .first()
    )


def _assets_by_types(
    db: Session, project_id: str, asset_types: set[AssetType]
) -> list[models.MediaAsset]:
    return (
        db.execute(
            select(models.MediaAsset)
            .where(
                models.MediaAsset.project_id == project_id,
                models.MediaAsset.type.in_([asset_type.value for asset_type in asset_types]),
            )
            .order_by(models.MediaAsset.type, models.MediaAsset.language, models.MediaAsset.created_at)
        )
        .scalars()
        .all()
    )


def language_label(language: str) -> str:
    return {
        "zh-CN": "中文原文",
        "en-US": "English",
        "es-ES": "Español",
        "es-MX": "Español",
        "pt-BR": "Português",
        "source": "原音轨",
        "auto": "Source",
    }.get(language, language)
