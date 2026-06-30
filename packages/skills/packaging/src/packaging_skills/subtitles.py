from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping


DEFAULT_MAX_LINE_CHARS = 42


@dataclass(frozen=True)
class SubtitleRenderResult:
    content: str
    quality_flags: list[dict[str, Any]] = field(default_factory=list)


def format_srt_timestamp(ms: int) -> str:
    hours, minutes, seconds, millis = _timestamp_parts(ms)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def format_vtt_timestamp(ms: int) -> str:
    hours, minutes, seconds, millis = _timestamp_parts(ms)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def select_active_translations(
    translations: Iterable[Mapping[str, Any]] | Mapping[str, Any],
    target_language: str,
) -> dict[str, str]:
    if isinstance(translations, Mapping):
        return _translations_from_mapping(translations, target_language)

    selected: dict[str, Mapping[str, Any]] = {}
    fallback: dict[str, Mapping[str, Any]] = {}
    for translation in translations:
        segment_id = str(translation.get("segment_id") or "")
        if not segment_id:
            continue
        language = translation.get("target_language") or translation.get("language")
        if language and str(language) != target_language:
            continue
        if str(translation.get("status") or "completed") != "completed":
            continue
        fallback.setdefault(segment_id, translation)
        if translation.get("active") is True:
            selected[segment_id] = translation

    for segment_id, translation in fallback.items():
        selected.setdefault(segment_id, translation)
    return {segment_id: str(translation.get("text") or "") for segment_id, translation in selected.items()}


def render_srt(
    segments: Iterable[Mapping[str, Any]],
    translations: Iterable[Mapping[str, Any]] | Mapping[str, Any],
    target_language: str,
    *,
    max_line_chars: int = DEFAULT_MAX_LINE_CHARS,
) -> SubtitleRenderResult:
    active = select_active_translations(translations, target_language)
    quality_flags: list[dict[str, Any]] = []
    blocks: list[str] = []
    for cue_index, segment in enumerate(_sorted_segments(segments), start=1):
        segment_id = str(segment.get("segment_id") or "")
        text, flags = _subtitle_text(segment, active, max_line_chars=max_line_chars)
        quality_flags.extend(flags)
        blocks.append(
            "\n".join(
                [
                    str(cue_index),
                    f"{format_srt_timestamp(_int_ms(segment.get('start_ms')))} --> "
                    f"{format_srt_timestamp(_int_ms(segment.get('end_ms')))}",
                    text,
                ]
            )
        )
    return SubtitleRenderResult("\n\n".join(blocks).rstrip() + ("\n" if blocks else ""), quality_flags)


def render_vtt(
    segments: Iterable[Mapping[str, Any]],
    translations: Iterable[Mapping[str, Any]] | Mapping[str, Any],
    target_language: str,
    *,
    max_line_chars: int = DEFAULT_MAX_LINE_CHARS,
) -> SubtitleRenderResult:
    active = select_active_translations(translations, target_language)
    quality_flags: list[dict[str, Any]] = []
    blocks = ["WEBVTT"]
    for segment in _sorted_segments(segments):
        text, flags = _subtitle_text(segment, active, max_line_chars=max_line_chars)
        quality_flags.extend(flags)
        blocks.append(
            "\n".join(
                [
                    f"{format_vtt_timestamp(_int_ms(segment.get('start_ms')))} --> "
                    f"{format_vtt_timestamp(_int_ms(segment.get('end_ms')))}",
                    text,
                ]
            )
        )
    return SubtitleRenderResult("\n\n".join(blocks).rstrip() + "\n", quality_flags)


def _translations_from_mapping(translations: Mapping[str, Any], target_language: str) -> dict[str, str]:
    selected: dict[str, str] = {}
    for segment_id, value in translations.items():
        if isinstance(value, Mapping):
            language = value.get("target_language") or value.get("language")
            if language and str(language) != target_language:
                continue
            if str(value.get("status") or "completed") != "completed":
                continue
            selected[str(segment_id)] = str(value.get("text") or "")
        else:
            selected[str(segment_id)] = str(value)
    return selected


def _subtitle_text(
    segment: Mapping[str, Any],
    active_translations: Mapping[str, str],
    *,
    max_line_chars: int,
) -> tuple[str, list[dict[str, Any]]]:
    segment_id = str(segment.get("segment_id") or "")
    text = _normalize_text(active_translations.get(segment_id, ""))
    flags: list[dict[str, Any]] = []
    if not text:
        flags.append(
            {
                "code": "MISSING_ACTIVE_TRANSLATION",
                "segment_id": segment_id,
                "message": "No active translation was available for subtitle generation",
            }
        )
        return "", flags

    wrapped = _two_line_text(text, max_line_chars=max_line_chars)
    if any(len(line) > max_line_chars for line in wrapped.splitlines()):
        flags.append(
            {
                "code": "SUBTITLE_TEXT_TOO_LONG",
                "segment_id": segment_id,
                "message": "Subtitle line exceeds recommended length",
            }
        )
    return wrapped, flags


def _two_line_text(text: str, *, max_line_chars: int = DEFAULT_MAX_LINE_CHARS) -> str:
    single_line = _normalize_text(text)
    if "\n" in single_line:
        lines = [line.strip() for line in single_line.splitlines() if line.strip()]
        single_line = " ".join(lines)
    if len(single_line) <= max_line_chars:
        return single_line
    words = single_line.split()
    if len(words) <= 1:
        return _split_compact_text(single_line)

    first: list[str] = []
    second: list[str] = []
    midpoint = len(single_line) / 2
    running = 0
    for index, word in enumerate(words):
        next_running = running + len(word) + (1 if first else 0)
        if not second and index > 0 and next_running >= midpoint:
            second = words[index:]
            break
        first.append(word)
        running = next_running
    if not second:
        return single_line
    return f"{' '.join(first)}\n{' '.join(second)}"


def _split_compact_text(text: str) -> str:
    midpoint = max(1, len(text) // 2)
    return f"{text[:midpoint]}\n{text[midpoint:]}"


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def _sorted_segments(segments: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(segments, key=lambda segment: (_int_ms(segment.get("start_ms")), int(segment.get("index") or 0)))


def _timestamp_parts(ms: int) -> tuple[int, int, int, int]:
    value = max(0, int(ms))
    seconds, millis = divmod(value, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return hours, minutes, seconds, millis


def _int_ms(value: object) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
