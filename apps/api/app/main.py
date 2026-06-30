from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.auth import AuthMiddleware
from app.config import Settings
from app.db import build_session_factory, create_schema
from app.domain.errors import ApiError, api_error_handler, validation_error_handler
from app.queue import build_queue
from app.routes import router
from app.runtime import InProcessAgentRuntime
from app.storage import SignedUrlObjectStorage


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(title="video-multisrt API", version="0.1.0")

    session_factory = build_session_factory(settings.database_url)
    if settings.create_schema:
        create_schema(session_factory)

    queue = build_queue(settings.redis_url)
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.queue = queue
    app.state.runtime = InProcessAgentRuntime(queue)
    app.state.storage = SignedUrlObjectStorage(
        settings.public_url_base,
        settings.storage_secret,
        settings.signed_url_ttl_seconds,
    )

    app.add_middleware(AuthMiddleware, auth_required=settings.auth_required)
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.include_router(router)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
