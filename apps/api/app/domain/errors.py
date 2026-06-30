from __future__ import annotations

from enum import StrEnum
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ErrorCode(StrEnum):
    INVALID_VIDEO = "INVALID_VIDEO"
    NO_AUDIO_TRACK = "NO_AUDIO_TRACK"
    VIDEO_TOO_LONG = "VIDEO_TOO_LONG"
    SOURCE_SEPARATION_FAILED = "SOURCE_SEPARATION_FAILED"
    ASR_FAILED = "ASR_FAILED"
    TRANSLATION_FAILED = "TRANSLATION_FAILED"
    TTS_FAILED = "TTS_FAILED"
    MIXING_FAILED = "MIXING_FAILED"
    PACKAGE_FAILED = "PACKAGE_FAILED"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    AGENT_RUN_FAILED = "AGENT_RUN_FAILED"
    SKILL_RUN_FAILED = "SKILL_RUN_FAILED"
    HUMAN_CHECKPOINT_REQUIRED = "HUMAN_CHECKPOINT_REQUIRED"
    INVALID_REQUEST = "INVALID_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    NOT_FOUND = "NOT_FOUND"


SPEC_ERROR_HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.INVALID_VIDEO: 422,
    ErrorCode.NO_AUDIO_TRACK: 422,
    ErrorCode.VIDEO_TOO_LONG: 422,
    ErrorCode.SOURCE_SEPARATION_FAILED: 502,
    ErrorCode.ASR_FAILED: 502,
    ErrorCode.TRANSLATION_FAILED: 502,
    ErrorCode.TTS_FAILED: 502,
    ErrorCode.MIXING_FAILED: 502,
    ErrorCode.PACKAGE_FAILED: 502,
    ErrorCode.PROVIDER_RATE_LIMITED: 429,
    ErrorCode.PROVIDER_UNAVAILABLE: 503,
    ErrorCode.AGENT_RUN_FAILED: 409,
    ErrorCode.SKILL_RUN_FAILED: 409,
    ErrorCode.HUMAN_CHECKPOINT_REQUIRED: 409,
    ErrorCode.INVALID_REQUEST: 422,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.NOT_FOUND: 404,
}


class ApiError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int | None = None,
        details: Any = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code or SPEC_ERROR_HTTP_STATUS[code]
        self.details = details
        super().__init__(message)


def error_payload(code: ErrorCode | str, message: str, details: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": str(code), "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=error_payload(exc.code, exc.message, exc.details),
    )


async def validation_error_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_payload(
            ErrorCode.INVALID_REQUEST,
            "Request validation failed",
            exc.errors(),
        ),
    )
