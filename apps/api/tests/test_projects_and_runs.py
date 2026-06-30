from __future__ import annotations

from app import models


def test_create_project_and_submit_processing(client, auth_headers, db_session):
    response = client.post(
        "/api/projects",
        headers=auth_headers,
        json={
            "name": "episode_01",
            "source_language": "auto",
            "target_languages": ["en-US", "es-ES"],
            "translation_style": "short_drama_localized",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"project_id", "upload_url"}
    assert body["project_id"].startswith("proj_")
    assert "expires=" in body["upload_url"]
    assert "signature=" in body["upload_url"]

    project_response = client.get(
        f"/api/projects/{body['project_id']}", headers=auth_headers
    )
    assert project_response.status_code == 200
    project_body = project_response.json()
    assert set(project_body) == {"project", "tasks", "assets", "languages"}
    assert project_body["project"]["status"] == "draft"
    assert project_body["languages"] == ["en-US", "es-ES"]
    assert project_body["assets"][0]["type"] == "source_video"
    assert project_body["assets"][0]["uri"].startswith("storage://private/")

    run_response = client.post(
        f"/api/projects/{body['project_id']}/process",
        headers=auth_headers,
        json={
            "enable_source_separation": True,
            "enable_diarization": True,
            "generate_tts": False,
            "generate_preview_mp4": False,
            "agent_template": "subtitle_draft",
        },
    )
    assert run_response.status_code == 200
    run_body = run_response.json()
    assert set(run_body) == {"run_id", "status"}
    assert run_body["status"] == "pending"

    query_run = client.get(f"/api/agent-runs/{run_body['run_id']}", headers=auth_headers)
    assert query_run.status_code == 200
    query_body = query_run.json()
    assert set(query_body) == {
        "agent_run",
        "skill_runs",
        "current_checkpoint",
        "quality_flags",
    }
    assert query_body["agent_run"]["template"] == "subtitle_draft"

    audits = db_session.query(models.AuditLog).order_by(models.AuditLog.created_at).all()
    assert [audit.action for audit in audits] == ["upload.requested", "process.submitted"]


def test_auth_required_for_api(client):
    response = client.get("/api/projects/proj_missing")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
