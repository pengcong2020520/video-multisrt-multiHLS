from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_VIDEO = "INVALID_VIDEO"
    NO_AUDIO_TRACK = "NO_AUDIO_TRACK"
    VIDEO_TOO_LONG = "VIDEO_TOO_LONG"
    SOURCE_SEPARATION_FAILED = "SOURCE_SEPARATION_FAILED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    SKILL_RUN_FAILED = "SKILL_RUN_FAILED"


class MediaSkillError(Exception):
    def __init__(self, code: ErrorCode | str, message: str) -> None:
        self.code = ErrorCode(code)
        self.message = message
        super().__init__(message)


class InvalidVideoError(MediaSkillError):
    def __init__(self, message: str = "Video format or codec is not supported") -> None:
        super().__init__(ErrorCode.INVALID_VIDEO, message)


class NoAudioTrackError(MediaSkillError):
    def __init__(self, message: str = "Video does not contain a usable audio track") -> None:
        super().__init__(ErrorCode.NO_AUDIO_TRACK, message)


class VideoTooLongError(MediaSkillError):
    def __init__(self, message: str = "Video exceeds the maximum supported duration") -> None:
        super().__init__(ErrorCode.VIDEO_TOO_LONG, message)


class SourceSeparationError(MediaSkillError):
    def __init__(self, message: str = "Source separation failed") -> None:
        super().__init__(ErrorCode.SOURCE_SEPARATION_FAILED, message)
