from __future__ import annotations

import json
from typing import Any


DEFAULT_PROMPT_VERSION = "short_drama_v1"

LANGUAGE_NAMES = {
    "zh-CN": "Simplified Chinese",
    "en-US": "American English",
    "es-ES": "Spanish for Spain",
    "es-MX": "Spanish for Mexico",
    "pt-BR": "Brazilian Portuguese",
}


def build_translation_messages(
    *,
    source_language: str,
    target_language: str,
    segments: list[dict[str, Any]],
    style: str,
    glossary: dict[str, str],
    character_notes: list[str],
    forbidden_terms: list[str],
    length_policy: Any,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
) -> list[dict[str, str]]:
    system = (
        "You are a senior localization translator for short-form drama. "
        "Translate dialogue for dubbing and subtitles, not word-for-word. "
        "Keep the relationship, emotion, suspense, reversals, and conflict strong. "
        "Use natural spoken lines in the target locale, avoid source-language phrasing, "
        "and keep proper nouns, names, titles, and recurring terms consistent. "
        "Shorten long lines when needed so the result can fit the original timing. "
        "Never use forbidden terms. Return valid JSON only."
    )

    payload = {
        "task": "localization.translate",
        "prompt_version": prompt_version,
        "source_language": source_language,
        "target_language": target_language,
        "target_locale_name": LANGUAGE_NAMES.get(target_language, target_language),
        "style": style,
        "glossary": glossary,
        "character_notes": character_notes,
        "forbidden_terms": forbidden_terms,
        "length_policy": length_policy,
        "segments": [
            {
                "segment_id": segment.get("segment_id"),
                "index": segment.get("index"),
                "start_ms": segment.get("start_ms"),
                "end_ms": segment.get("end_ms"),
                "speaker_id": segment.get("speaker_id"),
                "source_language": segment.get("source_language", source_language),
                "source_text": segment.get("source_text", ""),
            }
            for segment in segments
        ],
        "response_schema": {
            "translations": [
                {
                    "segment_id": "string",
                    "text": "localized target-language dialogue",
                    "quality_flags": [
                        {
                            "code": "string",
                            "message": "optional string",
                            "severity": "info|warning|error",
                        }
                    ],
                }
            ]
        },
    }
    user = (
        "Translate every segment into the requested target language. "
        "Use the exact segment_id values. Return JSON with a translations array only.\n"
        f"{json.dumps(payload, ensure_ascii=False, sort_keys=True)}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
