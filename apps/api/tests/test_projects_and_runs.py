from __future__ import annotations

from app import models
from app.domain.enums import AgentRunStatus


class FakeRuntime:
    def __init__(self):
        self.calls = []

    def create_run(
        self,
        db,
        project,
        *,
        version,
        template,
        created_by,
        target_languages,
        context,
    ):
        self.calls.append(
            {
                "project_id": project.project_id,
                "template": str(template),
                "target_languages": target_languages,
                "context": context,
            }
        )
        run = models.AgentRun(
            project_id=project.project_id,
            version_id=version.version_id,
            template=str(template),
            status=AgentRunStatus.PENDING.value,
            source_language=project.source_language,
            target_languages=target_languages,
            run_context={"config": context},
            created_by=created_by,
        )
        db.add(run)
        db.flush()
        return run

    def continue_run(self, db, run):
        run.status = AgentRunStatus.SUCCEEDED.value
        db.flush()
        return run


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
    assert set(body) == {"project_id", "upload_url", "preview_url"}
    assert body["project_id"].startswith("proj_")
    assert "expires=" in body["upload_url"]
    assert "signature=" in body["upload_url"]
    assert "expires=" in body["preview_url"]
    assert "signature=" in body["preview_url"]

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


def test_create_project_then_on_demand_translate_and_dub(client, auth_headers, db_session, app):
    fake_runtime = FakeRuntime()
    app.state.runtime = fake_runtime
    response = client.post(
        "/api/projects",
        headers=auth_headers,
        json={
            "name": "episode_02",
            "source_language": "auto",
        },
    )
    assert response.status_code == 200
    project_id = response.json()["project_id"]

    translate_response = client.post(
        f"/api/projects/{project_id}/translate",
        headers=auth_headers,
        json={"target_language": "en-US"},
    )
    assert translate_response.status_code == 200
    assert translate_response.json()["status"] == "pending"

    dub_response = client.post(
        f"/api/projects/{project_id}/dub",
        headers=auth_headers,
        json={"target_language": "es-ES"},
    )
    assert dub_response.status_code == 200
    assert dub_response.json()["status"] == "pending"

    assert [call["template"] for call in fake_runtime.calls] == [
        "subtitle_draft",
        "full_dubbing",
    ]
    assert fake_runtime.calls[0]["target_languages"] == ["en-US"]
    assert fake_runtime.calls[1]["target_languages"] == ["es-ES"]

    db_session.expire_all()
    project = db_session.get(models.Project, project_id)
    assert project is not None
    assert project.target_languages == ["en-US", "es-ES"]

    actions = [
        audit.action for audit in db_session.query(models.AuditLog).order_by(models.AuditLog.created_at)
    ]
    assert actions == ["upload.requested", "translate.requested", "dub.requested"]


def test_auth_required_for_api(client):
    response = client.get("/api/projects/proj_missing")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
