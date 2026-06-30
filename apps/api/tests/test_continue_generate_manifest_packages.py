from __future__ import annotations

from app import models
from app.domain.enums import AgentRunStatus, AgentTemplate, ProjectStatus
from tests.factories import seed_manifest_assets, seed_project, seed_segment_bundle


def test_continue_run_requires_waiting_human_and_saved_edit(
    client, auth_headers, db_session
):
    project, version = seed_project(db_session, status=ProjectStatus.PROOFREADING)
    segment, _, _ = seed_segment_bundle(db_session, project)
    run = models.AgentRun(
        project_id=project.project_id,
        version_id=version.version_id,
        template=AgentTemplate.FULL_DUBBING.value,
        status=AgentRunStatus.WAITING_HUMAN.value,
        checkpoint="proofreading",
        source_language=project.source_language,
        target_languages=project.target_languages,
        created_by="user_001",
    )
    db_session.add(run)
    db_session.commit()

    blocked = client.post(
        f"/api/agent-runs/{run.run_id}/continue",
        headers=auth_headers,
        json={"checkpoint": "proofreading", "confirmed": True},
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "HUMAN_CHECKPOINT_REQUIRED"

    edit = client.patch(
        f"/api/projects/{project.project_id}/segments/{segment.segment_id}",
        headers=auth_headers,
        json={"translations": {"en-US": "Edited line."}},
    )
    assert edit.status_code == 200

    continued = client.post(
        f"/api/agent-runs/{run.run_id}/continue",
        headers=auth_headers,
        json={"checkpoint": "proofreading", "confirmed": True},
    )
    assert continued.status_code == 200
    assert continued.json()["status"] == "running"


def test_generate_scope_validation_and_rerun(client, auth_headers, db_session):
    project, _ = seed_project(db_session, status=ProjectStatus.COMPLETED)
    segment, _, _ = seed_segment_bundle(db_session, project)
    db_session.commit()

    missing_segments = client.post(
        f"/api/projects/{project.project_id}/generate",
        headers=auth_headers,
        json={
            "target_language": "en-US",
            "scope": "segments",
            "steps": ["tts", "mix"],
            "segment_ids": [],
            "agent_template": "rerun_segments",
        },
    )
    assert missing_segments.status_code == 422

    wrong_template = client.post(
        f"/api/projects/{project.project_id}/generate",
        headers=auth_headers,
        json={
            "target_language": "en-US",
            "scope": "segments",
            "steps": ["tts", "mix"],
            "segment_ids": [segment.segment_id],
            "agent_template": "full_dubbing",
        },
    )
    assert wrong_template.status_code == 422

    response = client.post(
        f"/api/projects/{project.project_id}/generate",
        headers=auth_headers,
        json={
            "target_language": "en-US",
            "scope": "segments",
            "steps": ["tts", "mix"],
            "segment_ids": [segment.segment_id],
            "agent_template": "rerun_segments",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "pending"


def test_manifest_uses_signed_urls_and_package_request_is_audited(
    client, auth_headers, db_session
):
    project, version = seed_project(db_session, status=ProjectStatus.COMPLETED)
    seed_manifest_assets(db_session, project, version)
    db_session.commit()

    manifest_response = client.get(
        f"/api/projects/{project.project_id}/manifest?version_id={version.version_id}",
        headers=auth_headers,
    )
    assert manifest_response.status_code == 200
    manifest = manifest_response.json()
    assert manifest["project_id"] == project.project_id
    assert manifest["version_id"] == version.version_id
    assert "storage://private/" not in str(manifest)
    assert "expires=" in manifest["video"]["url"]
    assert "signature=" in manifest["video"]["url"]
    assert manifest["subtitles"][0]["format"] == "vtt"
    assert manifest["audio_tracks"][0]["language"] in {"source", "en-US"}
    assert manifest["downloads"][0]["type"] == "package_zip"

    package_response = client.post(
        f"/api/projects/{project.project_id}/packages",
        headers=auth_headers,
        json={
            "version_id": version.version_id,
            "languages": ["en-US", "es-ES"],
            "include_intermediate_assets": True,
        },
    )
    assert package_response.status_code == 200
    assert package_response.json()["package_id"].startswith("pkg_")
    assert package_response.json()["status"] == "pending"

    actions = {
        audit.action for audit in db_session.query(models.AuditLog).order_by(models.AuditLog.created_at)
    }
    assert {"download.manifest", "download.package_requested"}.issubset(actions)
