from __future__ import annotations

from app import models
from app.domain.enums import AssetType, ProjectStatus, TaskStatus, TranslationStatus
from app.domain.file_paths import private_uri, storage_key_for_asset


def seed_project(
    db,
    *,
    status: ProjectStatus = ProjectStatus.COMPLETED,
    source_language: str = "zh-CN",
    target_languages: list[str] | None = None,
) -> tuple[models.Project, models.Version]:
    project = models.Project(
        name="episode_01",
        status=status.value,
        source_language=source_language,
        target_languages=target_languages or ["en-US", "es-ES"],
        created_by="user_001",
        duration_ms=128000,
    )
    db.add(project)
    db.flush()
    version = models.Version(project_id=project.project_id, label="v1", created_by="user_001")
    db.add(version)
    db.flush()
    return project, version


def seed_segment_bundle(
    db, project: models.Project
) -> tuple[models.Segment, models.Translation, models.TTSJob]:
    segment = models.Segment(
        project_id=project.project_id,
        index=1,
        start_ms=1200,
        end_ms=3600,
        source_language="zh-CN",
        source_text="你到底想怎么样？",
        asr_confidence=0.92,
        locked=False,
        quality_flags=[],
    )
    db.add(segment)
    db.flush()
    translation = models.Translation(
        segment_id=segment.segment_id,
        target_language="en-US",
        text="What do you want?",
        style="short_drama_localized",
        model="deepseek-default",
        prompt_version="short_drama_v1",
        status=TranslationStatus.COMPLETED.value,
        active=True,
    )
    tts_job = models.TTSJob(
        project_id=project.project_id,
        segment_id=segment.segment_id,
        target_language="en-US",
        text=translation.text,
        voice_id="voice_en_female_01",
        target_duration_ms=2400,
        speed=1.0,
        status=TaskStatus.SUCCEEDED.value,
        provider="minimax",
    )
    db.add_all([translation, tts_job])
    db.flush()
    return segment, translation, tts_job


def seed_manifest_assets(db, project: models.Project, version: models.Version) -> None:
    assets = [
        models.MediaAsset(
            project_id=project.project_id,
            type=AssetType.SOURCE_VIDEO.value,
            uri=private_uri(storage_key_for_asset(project.project_id, AssetType.SOURCE_VIDEO)),
            format="mp4",
            duration_ms=project.duration_ms,
            version_id=version.version_id,
        ),
        models.MediaAsset(
            project_id=project.project_id,
            type=AssetType.SOURCE_AUDIO.value,
            uri=private_uri(storage_key_for_asset(project.project_id, AssetType.SOURCE_AUDIO)),
            format="wav",
            duration_ms=project.duration_ms,
            version_id=version.version_id,
        ),
        models.MediaAsset(
            project_id=project.project_id,
            type=AssetType.SUBTITLE_VTT.value,
            language="en-US",
            uri=private_uri(
                storage_key_for_asset(project.project_id, AssetType.SUBTITLE_VTT, language="en-US")
            ),
            format="vtt",
            version_id=version.version_id,
        ),
        models.MediaAsset(
            project_id=project.project_id,
            type=AssetType.TARGET_MIX_AUDIO.value,
            language="en-US",
            uri=private_uri(
                storage_key_for_asset(project.project_id, AssetType.TARGET_MIX_AUDIO, language="en-US")
            ),
            format="m4a",
            duration_ms=project.duration_ms,
            version_id=version.version_id,
        ),
        models.MediaAsset(
            project_id=project.project_id,
            type=AssetType.PACKAGE_ZIP.value,
            uri=private_uri(
                storage_key_for_asset(
                    project.project_id, AssetType.PACKAGE_ZIP, version_id=version.version_id
                )
            ),
            format="zip",
            version_id=version.version_id,
        ),
    ]
    db.add_all(assets)
    db.flush()
