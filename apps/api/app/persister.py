"""Concrete ``ResponsePersisterPort`` implementation for apps/api.

Maps skill ``SkillResponse`` outputs to SQLAlchemy rows in the API database:

* ``media.probe``                → updates ``Project.duration_ms``
* ``transcript.normalize_segments`` → writes ``Segment`` rows
* ``localization.translate``      → writes ``Translation`` rows
* ``voice.synthesize``            → writes ``TTSJob`` rows
* every skill                     → writes ``MediaAsset`` rows from ``response.assets``

This module is the single integration point between the (model-agnostic)
agent-runtime package and the (SQLAlchemy-bound) API models for persistence.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.domain.enums import TaskStatus, TranslationStatus

from agent_runtime.contracts import SkillResponse
from agent_runtime.persister import ResponsePersisterPort


class DatabaseResponsePersister(ResponsePersisterPort):
    """Persist skill outputs to the API database."""

    def persist(
        self,
        db: Session,
        *,
        project_id: str,
        run_id: str,
        skill_name: str,
        target_language: str | None,
        response: SkillResponse,
    ) -> None:
        if response.status != "succeeded":
            return

        outputs = response.outputs or {}

        try:
            if skill_name == "media.probe":
                self._persist_probe(db, project_id=project_id, outputs=outputs)
            if skill_name == "transcript.normalize_segments":
                self._persist_segments(db, project_id=project_id, outputs=outputs)
            if skill_name == "localization.translate":
                self._persist_translations(
                    db,
                    project_id=project_id,
                    target_language=target_language,
                    outputs=outputs,
                )
            if skill_name == "voice.synthesize":
                self._persist_tts_jobs(
                    db,
                    project_id=project_id,
                    target_language=target_language,
                    outputs=outputs,
                )

            # Every skill can emit asset rows.
            self._persist_assets(
                db,
                project_id=project_id,
                target_language=target_language,
                response=response,
            )
        except Exception:
            # Persistence must never break the run loop; the SkillRun row already
            # records the outcome.  Logging would go here in production.
            return

    # ------------------------------------------------------------------
    # Per-skill persistence helpers
    # ------------------------------------------------------------------

    def _persist_probe(
        self,
        db: Session,
        *,
        project_id: str,
        outputs: dict[str, Any],
    ) -> None:
        duration_ms = outputs.get("duration_ms")
        if duration_ms is None:
            return
        project = db.get(models.Project, project_id)
        if project is not None and project.duration_ms is None:
            project.duration_ms = int(duration_ms)

    def _persist_segments(
        self,
        db: Session,
        *,
        project_id: str,
        outputs: dict[str, Any],
    ) -> None:
        segments = outputs.get("segments")
        if not isinstance(segments, list) or not segments:
            return

        existing_ids = set(
            db.execute(
                select(models.Segment.segment_id).where(
                    models.Segment.project_id == project_id
                )
            ).scalars().all()
        )

        for item in segments:
            if not isinstance(item, dict):
                continue
            segment_id = str(item.get("segment_id") or "")
            if not segment_id or segment_id in existing_ids:
                continue
            index = _int_or_none(item.get("index")) or len(existing_ids)
            start_ms = _int_or_none(item.get("start_ms"))
            end_ms = _int_or_none(item.get("end_ms"))
            if start_ms is None or end_ms is None:
                continue
            db.add(
                models.Segment(
                    segment_id=segment_id,
                    project_id=project_id,
                    index=index,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    speaker_id=item.get("speaker_id"),
                    source_language=str(item.get("source_language") or ""),
                    source_text=str(item.get("source_text") or item.get("text") or ""),
                    asr_confidence=item.get("asr_confidence"),
                    locked=bool(item.get("locked") or False),
                    quality_flags=list(item.get("quality_flags") or []),
                )
            )
            existing_ids.add(segment_id)
        db.flush()

    def _persist_translations(
        self,
        db: Session,
        *,
        project_id: str,
        target_language: str | None,
        outputs: dict[str, Any],
    ) -> None:
        translations = outputs.get("translations") or outputs.get("active_translations")
        if not isinstance(translations, list) or not translations:
            return
        target_language = target_language or outputs.get("target_language")

        for item in translations:
            if not isinstance(item, dict):
                continue
            translation_id = str(item.get("translation_id") or "")
            segment_id = str(item.get("segment_id") or "")
            language = str(item.get("target_language") or target_language or "")
            if not translation_id or not segment_id or not language:
                continue

            existing = db.get(models.Translation, translation_id)
            if existing is not None:
                # Update in place to keep idempotency.
                existing.text = str(item.get("text") or existing.text)
                existing.active = bool(item.get("active", existing.active))
                existing.quality_flags = list(
                    item.get("quality_flags") or existing.quality_flags
                )
                if item.get("model") is not None:
                    existing.model = str(item.get("model"))
                continue

            # Deactivate prior active translations for this segment/language so
            # only the newly generated one is active.
            prior_actives = (
                db.execute(
                    select(models.Translation).where(
                        models.Translation.segment_id == segment_id,
                        models.Translation.target_language == language,
                        models.Translation.active.is_(True),
                    )
                ).scalars().all()
            )
            for prior in prior_actives:
                prior.active = False

            db.add(
                models.Translation(
                    translation_id=translation_id,
                    segment_id=segment_id,
                    target_language=language,
                    text=str(item.get("text") or ""),
                    style=str(item.get("style") or "short_drama_localized"),
                    model=item.get("model"),
                    prompt_version=item.get("prompt_version"),
                    status=str(item.get("status") or TranslationStatus.COMPLETED.value),
                    edited_by=item.get("edited_by"),
                    active=bool(item.get("active", True)),
                    quality_flags=list(item.get("quality_flags") or []),
                )
            )
        db.flush()

    def _persist_tts_jobs(
        self,
        db: Session,
        *,
        project_id: str,
        target_language: str | None,
        outputs: dict[str, Any],
    ) -> None:
        tts_jobs = outputs.get("tts_jobs")
        if not isinstance(tts_jobs, list) or not tts_jobs:
            return

        for item in tts_jobs:
            if not isinstance(item, dict):
                continue
            tts_job_id = str(item.get("tts_job_id") or "")
            segment_id = str(item.get("segment_id") or "")
            language = str(item.get("target_language") or target_language or "")
            if not tts_job_id or not segment_id or not language:
                continue

            existing = db.get(models.TTSJob, tts_job_id)
            if existing is not None:
                existing.status = str(item.get("status") or existing.status)
                existing.output_asset_id = item.get("output_asset_id") or existing.output_asset_id
                existing.actual_duration_ms = (
                    item.get("actual_duration_ms")
                    if item.get("actual_duration_ms") is not None
                    else existing.actual_duration_ms
                )
                existing.provider = item.get("provider") or existing.provider
                existing.provider_task_id = (
                    item.get("provider_task_id") or existing.provider_task_id
                )
                existing.error = item.get("error")
                existing.quality_flags = list(
                    item.get("quality_flags") or existing.quality_flags
                )
                continue

            target_duration_ms = _int_or_none(item.get("target_duration_ms")) or 0
            db.add(
                models.TTSJob(
                    tts_job_id=tts_job_id,
                    project_id=project_id,
                    segment_id=segment_id,
                    target_language=language,
                    text=str(item.get("text") or ""),
                    voice_id=item.get("voice_id"),
                    target_duration_ms=target_duration_ms,
                    speed=float(item.get("speed") or 1.0),
                    status=str(item.get("status") or TaskStatus.PENDING.value),
                    output_asset_id=item.get("output_asset_id"),
                    actual_duration_ms=item.get("actual_duration_ms"),
                    provider=item.get("provider"),
                    provider_task_id=item.get("provider_task_id"),
                    error=item.get("error"),
                    quality_flags=list(item.get("quality_flags") or []),
                )
            )
        db.flush()

    def _persist_assets(
        self,
        db: Session,
        *,
        project_id: str,
        target_language: str | None,
        response: SkillResponse,
    ) -> None:
        assets = response.assets or []
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            asset_id = str(asset.get("asset_id") or "")
            if not asset_id:
                continue
            existing = db.get(models.MediaAsset, asset_id)
            if existing is not None:
                continue
            asset_type = str(asset.get("type") or "")
            if not asset_type:
                continue
            db.add(
                models.MediaAsset(
                    asset_id=asset_id,
                    project_id=str(asset.get("project_id") or project_id),
                    type=asset_type,
                    language=asset.get("language") or target_language,
                    uri=str(asset.get("uri") or ""),
                    format=asset.get("format"),
                    duration_ms=_int_or_none(asset.get("duration_ms")),
                    size_bytes=_int_or_none(asset.get("size_bytes")),
                    checksum=asset.get("checksum"),
                    version_id=asset.get("version_id"),
                )
            )
        db.flush()


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = ["DatabaseResponsePersister"]
