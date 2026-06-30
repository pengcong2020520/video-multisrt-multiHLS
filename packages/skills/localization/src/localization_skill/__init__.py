from __future__ import annotations

from localization_skill.adapters import (
    DeepSeekTranslationAdapter,
    MockTranslationAdapter,
    TranslationAdapterError,
    TranslationAdapterPort,
    TranslationCandidate,
    TranslationRequest,
    TranslationResult,
    adapter_from_config,
)
from localization_skill.paths import private_uri, translation_json_path
from localization_skill.prompts import DEFAULT_PROMPT_VERSION, build_translation_messages
from localization_skill.quality import dedupe_quality_flags, translation_quality_flags
from localization_skill.skills import LocalizationSkillRunner, translate

__all__ = [
    "DEFAULT_PROMPT_VERSION",
    "DeepSeekTranslationAdapter",
    "LocalizationSkillRunner",
    "MockTranslationAdapter",
    "TranslationAdapterError",
    "TranslationAdapterPort",
    "TranslationCandidate",
    "TranslationRequest",
    "TranslationResult",
    "adapter_from_config",
    "build_translation_messages",
    "dedupe_quality_flags",
    "private_uri",
    "translate",
    "translation_json_path",
    "translation_quality_flags",
]
