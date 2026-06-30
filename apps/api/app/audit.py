from __future__ import annotations

from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app import models


def record_audit(
    db: Session,
    request: Request,
    *,
    action: str,
    actor_id: str,
    project_id: str | None = None,
    run_id: str | None = None,
    segment_id: str | None = None,
    asset_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> models.AuditLog:
    audit = models.AuditLog(
        actor_id=actor_id,
        action=action,
        project_id=project_id,
        run_id=run_id,
        segment_id=segment_id,
        asset_id=asset_id,
        request_path=request.url.path,
        method=request.method,
        metadata_json=metadata or {},
    )
    db.add(audit)
    return audit
