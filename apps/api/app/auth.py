from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.domain.errors import ErrorCode, error_payload


@dataclass(frozen=True)
class CurrentUser:
    user_id: str


def extract_user_id(request: Request) -> str | None:
    user_id = request.headers.get("X-User-Id")
    if user_id:
        return user_id
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        return token or None
    return None


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, auth_required: bool = True) -> None:
        super().__init__(app)
        self.auth_required = auth_required

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        user_id = extract_user_id(request)
        if not user_id and self.auth_required:
            return JSONResponse(
                status_code=401,
                content=error_payload(ErrorCode.UNAUTHORIZED, "Authentication required"),
            )
        request.state.user_id = user_id or "dev_user"
        return await call_next(request)


def current_user(request: Request) -> CurrentUser:
    return CurrentUser(user_id=getattr(request.state, "user_id", "dev_user"))
