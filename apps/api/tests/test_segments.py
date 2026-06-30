from __future__ import annotations

from app import models
from app.domain.enums import AssetType, ProjectStatus
from app.domain.file_paths import private_uri, storage_key_for_asset
from tests.factories import seed_project, seed_segment_bundle


def test_patch_segment_versions_translation_and_marks_downstream_stale(
    client, auth_headers, db_session
):
    project, _ = seed_project(db_session, status=ProjectStatus.PROOFREADING)
    segment, old_translation, tts_job = seed_segment_bundle(db_session, project)
    subtitle = models.MediaAsset(
        project_id=project.project_id,
        type=AssetType.SUBTITLE_VTT.value,
        language="en-US",
        uri=private_uri(
            storage_key_for_asset(project.project_id, AssetType.SUBTITLE_VTT, language="en-US")
        ),
        format="vtt",
        stale=False,
    )
    package = models.MediaAsset(
        project_id=project.project_id,
        type=AssetType.PACKAGE_ZIP.value,
        uri=private_uri(
            storage_key_for_asset(project.project_id, AssetType.PACKAGE_ZIP, version_id="ver_001")
        ),
        format="zip",
        stale=False,
    )
    db_session.add_all([subtitle, package])
    db_session.commit()

    response = client.patch(
        f"/api/projects/{project.project_id}/segments/{segment.segment_id}",
        headers=auth_headers,
        json={
            "start_ms": 1300,
            "end_ms": 3700,
            "translations": {"en-US": "What exactly do you want from me?"},
            "locked": True,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["segment"]["start_ms"] == 1300
    assert body["segment"]["locked"] is True
    assert body["translation"]["text"] == "What exactly do you want from me?"
    assert body["translation"]["edited_by"] == "user_001"

    db_session.expire_all()
    old = db_session.get(models.Translation, old_translation.translation_id)
    assert old.active is False
    active_translations = (
        db_session.query(models.Translation)
        .filter_by(segment_id=segment.segment_id, target_language="en-US", active=True)
        .all()
    )
    assert len(active_translations) == 1
    assert active_translations[0].edited_by == "user_001"
    assert db_session.query(models.SegmentVersion).count() == 1
    assert db_session.query(models.TranslationVersion).count() == 1
    assert db_session.get(models.TTSJob, tts_job.tts_job_id).stale is True
    assert db_session.get(models.MediaAsset, subtitle.asset_id).stale is True
    assert db_session.get(models.MediaAsset, package.asset_id).stale is True


def test_patch_segment_rejects_invalid_timeline(client, auth_headers, db_session):
    project, _ = seed_project(db_session, status=ProjectStatus.PROOFREADING)
    segment, _, _ = seed_segment_bundle(db_session, project)
    db_session.commit()

    response = client.patch(
        f"/api/projects/{project.project_id}/segments/{segment.segment_id}",
        headers=auth_headers,
        json={"start_ms": 5000, "end_ms": 4000},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_query_segments_returns_active_translation_and_tts_job(
    client, auth_headers, db_session
):
    project, _ = seed_project(db_session, status=ProjectStatus.PROOFREADING)
    segment, translation, tts_job = seed_segment_bundle(db_session, project)
    db_session.commit()

    response = client.get(
        f"/api/projects/{project.project_id}/segments?target_language=en-US",
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["segments"][0]["segment"]["segment_id"] == segment.segment_id
    assert body["segments"][0]["translation"]["translation_id"] == translation.translation_id
    assert body["segments"][0]["tts_job"]["tts_job_id"] == tts_job.tts_job_id
