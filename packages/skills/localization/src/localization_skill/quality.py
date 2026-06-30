from __future__ import annotations

from typing import Any


def quality_flag(
    code: str,
    message: str,
    *,
    severity: str = "warning",
    segment_id: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    flag: dict[str, Any] = {
        "code": code,
        "message": message,
        "severity": severity,
    }
    if segment_id:
        flag["segment_id"] = segment_id
    if language:
        flag["language"] = language
    return flag


def translation_quality_flags(
    *,
    segment: dict[str, Any],
    text: str,
    target_language: str,
    length_policy: Any,
    missing_from_provider: bool = False,
) -> list[dict[str, Any]]:
    segment_id = str(segment.get("segment_id") or "")
    flags: list[dict[str, Any]] = []
    stripped = text.strip()
    if not stripped:
        flags.append(
            quality_flag(
                "empty_translation",
                "Translation text is empty.",
                severity="error",
                segment_id=segment_id,
                language=target_language,
            )
        )
    if missing_from_provider or _target_language_missing(stripped, target_language):
        flags.append(
            quality_flag(
                "target_language_missing",
                "Translation does not appear to contain the target language.",
                severity="error" if not stripped else "warning",
                segment_id=segment_id,
                language=target_language,
            )
        )
    if _is_too_long(segment=segment, text=stripped, length_policy=length_policy):
        flags.append(
            quality_flag(
                "translation_too_long",
                "Translation may be too long for the source segment timing.",
                severity="warning",
                segment_id=segment_id,
                language=target_language,
            )
        )
    return dedupe_quality_flags(flags)


def dedupe_quality_flags(flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None, str | None]] = set()
    for flag in flags:
        code = str(flag.get("code") or "")
        if not code:
            continue
        key = (code, _optional_str(flag.get("segment_id")), _optional_str(flag.get("language")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(flag)
    return deduped


def _target_language_missing(text: str, target_language: str) -> bool:
    if not text:
        return True
    if target_language == "zh-CN":
        return not _has_cjk(text)
    if target_language in {"en-US", "es-ES", "es-MX", "pt-BR"}:
        return not _has_latin_letter(text) or _cjk_ratio(text) > 0.35
    return False


def _is_too_long(*, segment: dict[str, Any], text: str, length_policy: Any) -> bool:
    if not text:
        return False
    policy = _normalize_length_policy(length_policy)
    max_chars = policy.get("max_chars")
    if isinstance(max_chars, int) and max_chars > 0 and len(text) > max_chars:
        return True

    max_ratio = float(policy.get("max_ratio", 1.8))
    source_text = str(segment.get("source_text") or "")
    source_len = max(1, len("".join(source_text.split())))
    if len(text) > source_len * max_ratio + 8:
        return True

    max_chars_per_second = float(policy.get("max_chars_per_second", 22.0))
    duration_ms = _duration_ms(segment)
    if duration_ms > 0:
        chars_per_second = len(text) / max(duration_ms / 1000, 0.5)
        if chars_per_second > max_chars_per_second:
            return True
    return False


def _normalize_length_policy(policy: Any) -> dict[str, Any]:
    if isinstance(policy, dict):
        normalized = dict(policy)
    elif str(policy or "").lower() in {"strict", "tight"}:
        normalized = {"max_ratio": 1.4, "max_chars_per_second": 16.0}
    elif str(policy or "").lower() in {"loose", "relaxed"}:
        normalized = {"max_ratio": 2.2, "max_chars_per_second": 28.0}
    else:
        normalized = {"max_ratio": 1.8, "max_chars_per_second": 22.0}

    for key in ("max_chars", "max_chars_per_segment"):
        value = normalized.get(key)
        if value is not None:
            try:
                normalized["max_chars"] = int(value)
            except (TypeError, ValueError):
                normalized.pop("max_chars", None)
            break
    return normalized


def _duration_ms(segment: dict[str, Any]) -> int:
    try:
        return max(0, int(segment.get("end_ms") or 0) - int(segment.get("start_ms") or 0))
    except (TypeError, ValueError):
        return 0


def _has_cjk(text: str) -> bool:
    return any(0x4E00 <= ord(char) <= 0x9FFF for char in text)


def _cjk_ratio(text: str) -> float:
    letters = [char for char in text if not char.isspace()]
    if not letters:
        return 0.0
    return sum(1 for char in letters if 0x4E00 <= ord(char) <= 0x9FFF) / len(letters)


def _has_latin_letter(text: str) -> bool:
    for char in text:
        codepoint = ord(char)
        if "A" <= char <= "Z" or "a" <= char <= "z":
            return True
        if 0x00C0 <= codepoint <= 0x024F:
            return True
    return False


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None
