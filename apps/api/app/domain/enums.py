from __future__ import annotations

from enum import StrEnum


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    UPLOADED = "uploaded"
    PLANNING = "planning"
    PROCESSING = "processing"
    PROOFREADING = "proofreading"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class TaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"
    RETRYING = "retrying"


class AgentRunStatus(StrEnum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_HUMAN = "waiting_human"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class TaskType(StrEnum):
    PROBE_MEDIA = "probe_media"
    EXTRACT_AUDIO = "extract_audio"
    SEPARATE_SOURCES = "separate_sources"
    ASR = "asr"
    SEGMENT_NORMALIZE = "segment_normalize"
    TRANSLATE = "translate"
    GENERATE_SUBTITLE = "generate_subtitle"
    TTS = "tts"
    STITCH_TARGET_VOCAL = "stitch_target_vocal"
    MIX_AUDIO = "mix_audio"
    PACKAGE_OUTPUTS = "package_outputs"


class AgentTemplate(StrEnum):
    SUBTITLE_DRAFT = "subtitle_draft"
    FULL_DUBBING = "full_dubbing"
    RERUN_SEGMENTS = "rerun_segments"
    PACKAGE_ONLY = "package_only"


class AssetType(StrEnum):
    SOURCE_VIDEO = "source_video"
    SOURCE_AUDIO = "source_audio"
    SOURCE_VOCAL = "source_vocal"
    BACKGROUND_AUDIO = "background_audio"
    SUBTITLE_SRT = "subtitle_srt"
    SUBTITLE_VTT = "subtitle_vtt"
    TTS_SEGMENT_AUDIO = "tts_segment_audio"
    TARGET_VOCAL = "target_vocal"
    TARGET_MIX_AUDIO = "target_mix_audio"
    PREVIEW_VIDEO = "preview_video"
    PACKAGE_ZIP = "package_zip"


class TranslationStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class GenerateScope(StrEnum):
    LANGUAGE = "language"
    SEGMENTS = "segments"
    PACKAGE = "package"


class GenerateStep(StrEnum):
    SUBTITLE = "subtitle"
    TTS = "tts"
    MIX = "mix"


SOURCE_LANGUAGES = {"auto", "zh-CN", "en-US"}
TARGET_LANGUAGES = {"en-US", "zh-CN", "es-ES", "pt-BR", "es-MX"}
