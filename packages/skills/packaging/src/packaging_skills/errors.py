from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    MIXING_FAILED = "MIXING_FAILED"
    PACKAGE_FAILED = "PACKAGE_FAILED"
    SKILL_RUN_FAILED = "SKILL_RUN_FAILED"


class PackagingSkillError(Exception):
    def __init__(self, code: ErrorCode | str, message: str) -> None:
        self.code = ErrorCode(code)
        self.message = message
        super().__init__(message)
