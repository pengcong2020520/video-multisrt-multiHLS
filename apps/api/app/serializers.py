from __future__ import annotations

from typing import Any

from app import models


def project_to_dict(project: models.Project) -> dict[str, Any]:
    return {
        "project_id": project.project_id,
        "name": project.name,
        "status": project.status,
        "source_language": project.source_language,
        "target_languages": project.target_languages,
        "duration_ms": project.duration_ms,
        "created_by": project.created_by,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
    }


def asset_to_dict(asset: models.MediaAsset) -> dict[str, Any]:
    return {
        "asset_id": asset.asset_id,
        "project_id": asset.project_id,
        "type": asset.type,
        "language": asset.language,
        "uri": asset.uri,
        "format": asset.format,
        "duration_ms": asset.duration_ms,
        "size_bytes": asset.size_bytes,
        "checksum": asset.checksum,
        "created_at": asset.created_at,
    }


def segment_to_dict(segment: models.Segment) -> dict[str, Any]:
    return {
        "segment_id": segment.segment_id,
        "project_id": segment.project_id,
        "index": segment.index,
        "start_ms": segment.start_ms,
        "end_ms": segment.end_ms,
        "speaker_id": segment.speaker_id,
        "source_language": segment.source_language,
        "source_text": segment.source_text,
        "asr_confidence": segment.asr_confidence,
        "locked": segment.locked,
        "quality_flags": segment.quality_flags,
    }


def translation_to_dict(translation: models.Translation | None) -> dict[str, Any] | None:
    if translation is None:
        return None
    return {
        "translation_id": translation.translation_id,
        "segment_id": translation.segment_id,
        "target_language": translation.target_language,
        "text": translation.text,
        "style": translation.style,
        "model": translation.model,
        "prompt_version": translation.prompt_version,
        "status": translation.status,
        "edited_by": translation.edited_by,
        "updated_at": translation.updated_at,
    }


def tts_job_to_dict(tts_job: models.TTSJob | None) -> dict[str, Any] | None:
    if tts_job is None:
        return None
    return {
        "tts_job_id": tts_job.tts_job_id,
        "project_id": tts_job.project_id,
        "segment_id": tts_job.segment_id,
        "target_language": tts_job.target_language,
        "text": tts_job.text,
        "voice_id": tts_job.voice_id,
        "target_duration_ms": tts_job.target_duration_ms,
        "speed": tts_job.speed,
        "status": tts_job.status,
        "output_asset_id": tts_job.output_asset_id,
        "actual_duration_ms": tts_job.actual_duration_ms,
        "provider": tts_job.provider,
        "provider_task_id": tts_job.provider_task_id,
        "error": tts_job.error,
    }


def agent_run_to_dict(agent_run: models.AgentRun) -> dict[str, Any]:
    return {
        "run_id": agent_run.run_id,
        "project_id": agent_run.project_id,
        "version_id": agent_run.version_id,
        "template": agent_run.template,
        "status": agent_run.status,
        "current_step": agent_run.current_step,
        "source_language": agent_run.source_language,
        "target_languages": agent_run.target_languages,
        "created_by": agent_run.created_by,
        "created_at": agent_run.created_at,
        "updated_at": agent_run.updated_at,
    }


def skill_run_to_dict(skill_run: models.SkillRun) -> dict[str, Any]:
    return {
        "skill_run_id": skill_run.skill_run_id,
        "run_id": skill_run.run_id,
        "project_id": skill_run.project_id,
        "skill_name": skill_run.skill_name,
        "skill_version": skill_run.skill_version,
        "status": skill_run.status,
        "target_language": skill_run.target_language,
        "started_at": skill_run.started_at,
        "finished_at": skill_run.finished_at,
        "input_refs": skill_run.input_refs,
        "output_refs": skill_run.output_refs,
        "provider": skill_run.provider,
        "model": skill_run.model,
        "error": skill_run.error,
    }


def task_to_dict(task: models.Task) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "project_id": task.project_id,
        "run_id": task.run_id,
        "type": task.type,
        "status": task.status,
        "target_language": task.target_language,
        "error_code": task.error_code,
        "error_message": task.error_message,
        "retry_count": task.retry_count,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }
