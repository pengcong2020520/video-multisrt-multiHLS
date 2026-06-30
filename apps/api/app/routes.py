from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.auth import CurrentUser, current_user
from app.db import get_db
from app.schemas import (
    ContinueRunRequest,
    CreateProjectRequest,
    CreateProjectResponse,
    GenerateProjectRequest,
    ManifestResponse,
    PackageRequestBody,
    PackageResponse,
    PatchSegmentRequest,
    ProcessProjectRequest,
    QueryAgentRunResponse,
    QueryProjectResponse,
    QuerySegmentsResponse,
    RunResponse,
    SegmentBundle,
)
from app import services

router = APIRouter(prefix="/api")

DbSession = Annotated[Session, Depends(get_db)]
User = Annotated[CurrentUser, Depends(current_user)]


@router.post("/projects", response_model=CreateProjectResponse)
def create_project(
    payload: CreateProjectRequest,
    request: Request,
    db: DbSession,
    user: User,
) -> CreateProjectResponse:
    project, upload_url = services.create_project(
        db, request.app.state.storage, payload, actor_id=user.user_id
    )
    record_audit(
        db,
        request,
        action="upload.requested",
        actor_id=user.user_id,
        project_id=project.project_id,
        metadata={"name": payload.name, "target_languages": payload.target_languages},
    )
    db.commit()
    return CreateProjectResponse(project_id=project.project_id, upload_url=upload_url)


@router.post("/projects/{project_id}/process", response_model=RunResponse)
def process_project(
    project_id: str,
    payload: ProcessProjectRequest,
    request: Request,
    db: DbSession,
    user: User,
) -> RunResponse:
    run = services.submit_processing(
        db, request.app.state.runtime, project_id, payload, actor_id=user.user_id
    )
    record_audit(
        db,
        request,
        action="process.submitted",
        actor_id=user.user_id,
        project_id=project_id,
        run_id=run.run_id,
        metadata=payload.model_dump(mode="json"),
    )
    db.commit()
    return RunResponse(run_id=run.run_id, status=run.status)


@router.get("/agent-runs/{run_id}", response_model=QueryAgentRunResponse)
def get_agent_run(run_id: str, db: DbSession, _: User) -> dict:
    return services.query_agent_run(db, run_id)


@router.post("/agent-runs/{run_id}/continue", response_model=RunResponse)
def continue_run(
    run_id: str,
    payload: ContinueRunRequest,
    request: Request,
    db: DbSession,
    user: User,
) -> RunResponse:
    run = services.continue_agent_run(db, request.app.state.runtime, run_id, payload)
    record_audit(
        db,
        request,
        action="agent_run.continue",
        actor_id=user.user_id,
        project_id=run.project_id,
        run_id=run.run_id,
        metadata=payload.model_dump(mode="json"),
    )
    db.commit()
    return RunResponse(run_id=run.run_id, status=run.status)


@router.get("/projects/{project_id}", response_model=QueryProjectResponse)
def get_project(project_id: str, db: DbSession, _: User) -> dict:
    return services.query_project(db, project_id)


@router.get("/projects/{project_id}/segments", response_model=QuerySegmentsResponse)
def get_segments(
    project_id: str,
    db: DbSession,
    _: User,
    target_language: str | None = Query(default=None),
) -> dict:
    return services.query_segments(db, project_id, target_language)


@router.patch("/projects/{project_id}/segments/{segment_id}", response_model=SegmentBundle)
def patch_segment(
    project_id: str,
    segment_id: str,
    payload: PatchSegmentRequest,
    request: Request,
    db: DbSession,
    user: User,
) -> dict:
    bundle = services.update_segment(db, project_id, segment_id, payload, actor_id=user.user_id)
    record_audit(
        db,
        request,
        action="segment.update",
        actor_id=user.user_id,
        project_id=project_id,
        segment_id=segment_id,
        metadata=payload.model_dump(exclude_unset=True, mode="json"),
    )
    db.commit()
    return bundle


@router.post("/projects/{project_id}/generate", response_model=RunResponse)
def generate_project(
    project_id: str,
    payload: GenerateProjectRequest,
    request: Request,
    db: DbSession,
    user: User,
) -> RunResponse:
    run = services.generate_project(
        db, request.app.state.runtime, project_id, payload, actor_id=user.user_id
    )
    record_audit(
        db,
        request,
        action="generate.requested",
        actor_id=user.user_id,
        project_id=project_id,
        run_id=run.run_id,
        metadata=payload.model_dump(mode="json"),
    )
    db.commit()
    return RunResponse(run_id=run.run_id, status=run.status)


@router.get("/projects/{project_id}/manifest", response_model=ManifestResponse)
def get_manifest(
    project_id: str,
    request: Request,
    db: DbSession,
    user: User,
    version_id: str | None = Query(default=None),
) -> dict:
    manifest = services.get_manifest(db, request.app.state.storage, project_id, version_id)
    record_audit(
        db,
        request,
        action="download.manifest",
        actor_id=user.user_id,
        project_id=project_id,
        metadata={"version_id": manifest["version_id"]},
    )
    db.commit()
    return manifest


@router.post("/projects/{project_id}/packages", response_model=PackageResponse)
def create_package(
    project_id: str,
    payload: PackageRequestBody,
    request: Request,
    db: DbSession,
    user: User,
) -> PackageResponse:
    package = services.request_package(
        db, request.app.state.queue, project_id, payload, actor_id=user.user_id
    )
    record_audit(
        db,
        request,
        action="download.package_requested",
        actor_id=user.user_id,
        project_id=project_id,
        metadata=payload.model_dump(mode="json") | {"package_id": package.package_id},
    )
    db.commit()
    return PackageResponse(package_id=package.package_id, status=package.status)
