from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any


SENTENCE_RE = re.compile(r"[^。！？!?\.]+[。！？!?\.]?")


@dataclass(frozen=True)
class NormalizeOptions:
    min_duration_ms: int = 800
    max_duration_ms: int = 8000
    max_merge_gap_ms: int = 600
    max_silence_ms: int = 1200


@dataclass
class _Candidate:
    start_ms: int
    end_ms: int
    text: str
    speaker_label: str | None
    confidence: float | None
    flags: list[dict[str, Any]]

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


def normalize_transcript_segments(
    raw_transcript: dict[str, Any] | list[dict[str, Any]],
    *,
    project_id: str,
    source_language: str,
    speaker_timeline: list[dict[str, Any]] | None = None,
    locked_segments: list[dict[str, Any]] | None = None,
    locked_segment_ids: list[str] | None = None,
    reserved_segment_ids: list[str] | None = None,
    options: NormalizeOptions | None = None,
) -> dict[str, Any]:
    options = options or NormalizeOptions()
    transcript = _as_transcript(raw_transcript)
    detected_language = transcript.get("detected_language")
    language = _segment_language(source_language, detected_language)
    timeline = _coerce_timeline(speaker_timeline or transcript.get("speaker_timeline") or [])
    locked = _locked_segments(locked_segments or [])
    locked_ids = set(locked_segment_ids or [])
    locked_ids.update(item["segment_id"] for item in locked if item.get("segment_id"))
    reserved_ids = set(reserved_segment_ids or [])
    reserved_ids.update(locked_ids)

    global_flags: list[dict[str, Any]] = []
    candidates = _prepare_candidates(transcript.get("segments") or transcript.get("raw_segments") or [], options)
    candidates = _merge_short_candidates(candidates, options)
    candidates = _apply_min_duration(candidates, options)

    speaker_id_for_label = _stable_speaker_id_mapper(timeline, candidates)
    segments: list[dict[str, Any]] = []
    skipped_locked_ids: list[str] = []
    next_index = 1
    for candidate in candidates:
        overlap_locked = _overlapping_locked(candidate, locked)
        if overlap_locked is not None:
            skipped_locked_ids.append(overlap_locked["segment_id"])
            global_flags.append(
                _quality_flag(
                    "locked_overlap_skipped",
                    "Generated ASR segment overlaps a locked segment and was not emitted.",
                    severity="warning",
                    segment_id=overlap_locked.get("segment_id"),
                )
            )
            continue

        if candidate.start_ms >= candidate.end_ms:
            global_flags.append(
                _quality_flag("invalid_timing", "Segment start_ms must be less than end_ms.", severity="error")
            )
            continue

        speaker_label = candidate.speaker_label or _speaker_for_interval(candidate, timeline)
        speaker_id = speaker_id_for_label(speaker_label)
        segment_id = _next_segment_id(reserved_ids, next_index)
        reserved_ids.add(segment_id)
        next_index += 1
        flags = list(candidate.flags)
        if candidate.duration_ms < options.min_duration_ms:
            flags.append(
                _quality_flag("too_short", "Segment is shorter than the recommended 0.8 seconds.")
            )
        if candidate.duration_ms > options.max_duration_ms:
            flags.append(
                _quality_flag("too_long", "Segment is longer than the recommended 8 seconds.", severity="warning")
            )
        for flag in flags:
            flag.setdefault("segment_id", segment_id)
        segments.append(
            {
                "segment_id": segment_id,
                "project_id": project_id,
                "index": len(segments) + 1,
                "start_ms": candidate.start_ms,
                "end_ms": candidate.end_ms,
                "speaker_id": speaker_id,
                "source_language": language,
                "source_text": candidate.text,
                "asr_confidence": candidate.confidence,
                "locked": False,
                "quality_flags": flags,
            }
        )

    return {
        "segments": segments,
        "quality_flags": _dedupe_flags(global_flags),
        "skipped_locked_segment_ids": list(dict.fromkeys(skipped_locked_ids)),
    }


def normalize_speaker_timeline(
    speaker_timeline: list[dict[str, Any]],
    *,
    project_id: str,
) -> dict[str, Any]:
    turns = _coerce_timeline(speaker_timeline)
    speaker_map: dict[str, str] = {}
    normalized_turns: list[dict[str, Any]] = []
    for turn in turns:
        if turn["start_ms"] >= turn["end_ms"]:
            continue
        speaker_id = _stable_speaker_id(turn["speaker_id"], speaker_map)
        normalized_turns.append(
            {
                "start_ms": turn["start_ms"],
                "end_ms": turn["end_ms"],
                "speaker_id": speaker_id,
                "confidence": turn.get("confidence"),
            }
        )
    speakers = [
        {
            "speaker_id": speaker_id,
            "project_id": project_id,
            "display_name": f"Speaker {index}",
            "source_voice_sample_asset_id": None,
            "target_voice_map": {},
        }
        for index, speaker_id in enumerate(dict.fromkeys(turn["speaker_id"] for turn in normalized_turns), start=1)
    ]
    return {"speaker_timeline": normalized_turns, "speakers": speakers}


def _as_transcript(value: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(value, list):
        return {"segments": value, "detected_language": None, "speaker_timeline": []}
    if "raw_segments" in value and "segments" not in value:
        value = dict(value)
        value["segments"] = value["raw_segments"]
    return value


def _prepare_candidates(raw_segments: list[dict[str, Any]], options: NormalizeOptions) -> list[_Candidate]:
    candidates: list[_Candidate] = []
    for raw in sorted(raw_segments, key=lambda item: _time_to_ms(item.get("start_ms", item.get("start", 0)))):
        text = " ".join(str(raw.get("text") or "").split())
        if not text:
            continue
        start_ms = _time_to_ms(raw.get("start_ms", raw.get("start", 0)))
        end_ms = _time_to_ms(raw.get("end_ms", raw.get("end", 0)))
        if start_ms >= end_ms:
            continue
        speaker = _optional_str(raw.get("speaker_id") or raw.get("speaker"))
        confidence = _clip_confidence(raw.get("confidence") or raw.get("score"))
        base = _Candidate(start_ms, end_ms, text, speaker, confidence, [])
        candidates.extend(_split_overlong_candidate(base, options))
    return candidates


def _split_overlong_candidate(candidate: _Candidate, options: NormalizeOptions) -> list[_Candidate]:
    if candidate.duration_ms <= options.max_duration_ms:
        return [candidate]
    piece_count = math.ceil(candidate.duration_ms / options.max_duration_ms)
    text_pieces = _split_text(candidate.text, piece_count)
    pieces: list[_Candidate] = []
    for index in range(piece_count):
        start = candidate.start_ms + round(candidate.duration_ms * index / piece_count)
        end = candidate.start_ms + round(candidate.duration_ms * (index + 1) / piece_count)
        flags = list(candidate.flags)
        flags.append(
            _quality_flag("split_long_segment", "Raw ASR segment was split to stay within 8 seconds.")
        )
        pieces.append(
            _Candidate(
                start_ms=start,
                end_ms=end,
                text=text_pieces[index] if index < len(text_pieces) else candidate.text,
                speaker_label=candidate.speaker_label,
                confidence=candidate.confidence,
                flags=flags,
            )
        )
    return pieces


def _merge_short_candidates(candidates: list[_Candidate], options: NormalizeOptions) -> list[_Candidate]:
    if not candidates:
        return []
    merged: list[_Candidate] = []
    current = candidates[0]
    for next_candidate in candidates[1:]:
        gap = next_candidate.start_ms - current.end_ms
        can_merge = (
            current.duration_ms < options.min_duration_ms
            and 0 <= gap <= options.max_merge_gap_ms
            and current.end_ms - current.start_ms + gap + next_candidate.duration_ms <= options.max_duration_ms
            and _compatible_speaker(current.speaker_label, next_candidate.speaker_label)
        )
        if can_merge:
            current = _merge_candidates(current, next_candidate)
            continue
        if gap > options.max_silence_ms:
            current.flags.append(
                _quality_flag("long_silence_after", "Segment boundary preserves a long silence.")
            )
        merged.append(current)
        current = next_candidate
    merged.append(current)
    return merged


def _apply_min_duration(candidates: list[_Candidate], options: NormalizeOptions) -> list[_Candidate]:
    adjusted: list[_Candidate] = []
    for index, candidate in enumerate(candidates):
        if candidate.duration_ms >= options.min_duration_ms:
            adjusted.append(candidate)
            continue
        next_start = candidates[index + 1].start_ms if index + 1 < len(candidates) else None
        desired_end = candidate.start_ms + options.min_duration_ms
        if next_start is not None:
            desired_end = min(desired_end, next_start)
        if desired_end > candidate.end_ms:
            candidate = _Candidate(
                start_ms=candidate.start_ms,
                end_ms=desired_end,
                text=candidate.text,
                speaker_label=candidate.speaker_label,
                confidence=candidate.confidence,
                flags=list(candidate.flags)
                + [_quality_flag("duration_extended", "Short segment end_ms was extended to meet 0.8 seconds.")],
            )
        adjusted.append(candidate)
    return adjusted


def _merge_candidates(left: _Candidate, right: _Candidate) -> _Candidate:
    confidences = [value for value in (left.confidence, right.confidence) if value is not None]
    confidence = sum(confidences) / len(confidences) if confidences else None
    return _Candidate(
        start_ms=left.start_ms,
        end_ms=right.end_ms,
        text=f"{left.text} {right.text}".strip(),
        speaker_label=left.speaker_label or right.speaker_label,
        confidence=confidence,
        flags=list(left.flags) + list(right.flags),
    )


def _split_text(text: str, piece_count: int) -> list[str]:
    sentences = [match.group(0).strip() for match in SENTENCE_RE.finditer(text) if match.group(0).strip()]
    tokens = sentences if len(sentences) >= piece_count else text.split()
    if not tokens:
        tokens = list(text)
    if len(tokens) <= piece_count:
        return tokens + [""] * (piece_count - len(tokens))

    result: list[str] = []
    for index in range(piece_count):
        start = round(len(tokens) * index / piece_count)
        end = round(len(tokens) * (index + 1) / piece_count)
        joiner = "" if tokens is not None and tokens == list(text) else " "
        result.append(joiner.join(tokens[start:end]).strip())
    return result


def _coerce_timeline(raw_timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for raw in raw_timeline:
        speaker = raw.get("speaker_id") or raw.get("speaker") or raw.get("label")
        if not speaker:
            continue
        timeline.append(
            {
                "start_ms": _time_to_ms(raw.get("start_ms", raw.get("start", 0))),
                "end_ms": _time_to_ms(raw.get("end_ms", raw.get("end", 0))),
                "speaker_id": str(speaker),
                "confidence": _clip_confidence(raw.get("confidence") or raw.get("score")),
            }
        )
    return sorted(timeline, key=lambda item: (item["start_ms"], item["end_ms"]))


def _locked_segments(raw_segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    locked: list[dict[str, Any]] = []
    for raw in raw_segments:
        if raw.get("locked") is not True:
            continue
        segment_id = raw.get("segment_id")
        if not segment_id:
            continue
        locked.append(
            {
                "segment_id": str(segment_id),
                "start_ms": _time_to_ms(raw.get("start_ms", raw.get("start", 0))),
                "end_ms": _time_to_ms(raw.get("end_ms", raw.get("end", 0))),
            }
        )
    return locked


def _overlapping_locked(candidate: _Candidate, locked: list[dict[str, Any]]) -> dict[str, Any] | None:
    for segment in locked:
        overlap = min(candidate.end_ms, segment["end_ms"]) - max(candidate.start_ms, segment["start_ms"])
        if overlap > 0:
            return segment
    return None


def _stable_speaker_id_mapper(
    timeline: list[dict[str, Any]],
    candidates: list[_Candidate],
):
    speaker_map: dict[str, str] = {}
    for turn in timeline:
        _stable_speaker_id(turn["speaker_id"], speaker_map)
    for candidate in candidates:
        if candidate.speaker_label:
            _stable_speaker_id(candidate.speaker_label, speaker_map)

    def mapper(label: str | None) -> str | None:
        if label is None:
            return None
        return _stable_speaker_id(label, speaker_map)

    return mapper


def _stable_speaker_id(label: str, speaker_map: dict[str, str]) -> str:
    if re.fullmatch(r"spk_\d+", label):
        speaker_map.setdefault(label, label)
        return label
    if label not in speaker_map:
        used = [
            int(value.removeprefix("spk_"))
            for value in speaker_map.values()
            if re.fullmatch(r"spk_\d+", value)
        ]
        speaker_map[label] = f"spk_{(max(used) if used else 0) + 1}"
    return speaker_map[label]


def _speaker_for_interval(candidate: _Candidate, timeline: list[dict[str, Any]]) -> str | None:
    best_label: str | None = None
    best_overlap = 0
    for turn in timeline:
        overlap = min(candidate.end_ms, turn["end_ms"]) - max(candidate.start_ms, turn["start_ms"])
        if overlap > best_overlap:
            best_overlap = overlap
            best_label = turn["speaker_id"]
    return best_label


def _compatible_speaker(left: str | None, right: str | None) -> bool:
    return left is None or right is None or left == right


def _next_segment_id(reserved: set[str], start_index: int) -> str:
    index = start_index
    while True:
        segment_id = f"seg_{index:04d}"
        if segment_id not in reserved:
            return segment_id
        index += 1


def _segment_language(source_language: str, detected_language: Any) -> str:
    if isinstance(detected_language, str) and detected_language and detected_language != "auto":
        return detected_language
    return source_language or "auto"


def _time_to_ms(value: Any) -> int:
    if isinstance(value, str):
        value = float(value)
    if isinstance(value, float) and value < 1000:
        return int(round(value * 1000))
    return int(round(float(value)))


def _clip_confidence(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, numeric))


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _quality_flag(
    code: str,
    message: str,
    *,
    severity: str = "info",
    segment_id: str | None = None,
) -> dict[str, Any]:
    flag: dict[str, Any] = {"code": code, "message": message, "severity": severity}
    if segment_id:
        flag["segment_id"] = segment_id
    return flag


def _dedupe_flags(flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for flag in flags:
        key = (str(flag.get("code")), flag.get("segment_id"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(flag)
    return deduped
