from __future__ import annotations

from typing import Any


def success_response(
    outputs: dict[str, Any] | None = None,
    *,
    assets: list[dict[str, Any]] | None = None,
    quality_flags: list[dict[str, Any]] | None = None,
    usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "succeeded",
        "outputs": outputs or {},
        "assets": assets or [],
        "quality_flags": quality_flags or [],
        "usage": usage or {},
        "error": None,
    }


def failure_response(
    code: str,
    message: str,
    *,
    outputs: dict[str, Any] | None = None,
    assets: list[dict[str, Any]] | None = None,
    quality_flags: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "status": "failed",
        "outputs": outputs or {},
        "assets": assets or [],
        "quality_flags": quality_flags or [],
        "usage": {},
        "error": {"code": code, "message": message},
    }
