from __future__ import annotations

from asr_skill.normalization import NormalizeOptions, normalize_speaker_timeline, normalize_transcript_segments


def test_normalizes_transcript_timeline_without_crossing_long_silence() -> None:
    result = normalize_transcript_segments(
        {
            "detected_language": "en-US",
            "segments": [
                {"start_ms": 0, "end_ms": 500, "text": "Hi", "confidence": 0.8},
                {"start_ms": 650, "end_ms": 1600, "text": "there", "confidence": 0.9},
                {"start_ms": 4200, "end_ms": 5200, "text": "After pause", "confidence": 0.7},
            ],
        },
        project_id="proj_123",
        source_language="auto",
        speaker_timeline=[
            {"start_ms": 0, "end_ms": 2000, "speaker": "SPEAKER_00"},
            {"start_ms": 4000, "end_ms": 6000, "speaker": "SPEAKER_01"},
        ],
    )

    segments = result["segments"]
    assert [segment["source_text"] for segment in segments] == ["Hi there", "After pause"]
    assert [(segment["start_ms"], segment["end_ms"]) for segment in segments] == [(0, 1600), (4200, 5200)]
    assert [segment["speaker_id"] for segment in segments] == ["spk_1", "spk_2"]
    assert all(segment["start_ms"] < segment["end_ms"] for segment in segments)
    assert all(segment["end_ms"] - segment["start_ms"] <= 8000 for segment in segments)


def test_handles_too_short_too_long_and_empty_text() -> None:
    result = normalize_transcript_segments(
        {
            "detected_language": "zh-CN",
            "segments": [
                {"start_ms": 0, "end_ms": 400, "text": "短"},
                {"start_ms": 1200, "end_ms": 1900, "text": ""},
                {
                    "start_ms": 2000,
                    "end_ms": 19000,
                    "text": "第一句。第二句。第三句。",
                },
                {"start_ms": 21000, "end_ms": 21000, "text": "bad"},
            ],
        },
        project_id="proj_123",
        source_language="zh-CN",
    )

    segments = result["segments"]
    assert [segment["source_text"] for segment in segments] == ["短", "第一句。", "第二句。", "第三句。"]
    assert segments[0]["end_ms"] - segments[0]["start_ms"] == 800
    assert "duration_extended" in {flag["code"] for flag in segments[0]["quality_flags"]}
    assert all(segment["source_text"] for segment in segments)
    assert all(segment["start_ms"] < segment["end_ms"] for segment in segments)
    assert all(segment["end_ms"] - segment["start_ms"] <= 8000 for segment in segments)
    assert {
        flag["code"]
        for segment in segments
        for flag in segment["quality_flags"]
    } >= {"split_long_segment", "duration_extended"}


def test_diarization_speaker_ids_are_stable() -> None:
    normalized = normalize_speaker_timeline(
        [
            {"start_ms": 0, "end_ms": 1000, "speaker": "SPEAKER_01"},
            {"start_ms": 1000, "end_ms": 2000, "speaker": "SPEAKER_00"},
            {"start_ms": 2000, "end_ms": 3000, "speaker": "SPEAKER_01"},
        ],
        project_id="proj_123",
    )

    assert [turn["speaker_id"] for turn in normalized["speaker_timeline"]] == ["spk_1", "spk_2", "spk_1"]
    assert [speaker["speaker_id"] for speaker in normalized["speakers"]] == ["spk_1", "spk_2"]
    assert normalized["speakers"][0]["display_name"] == "Speaker 1"


def test_locked_segments_are_not_overwritten() -> None:
    result = normalize_transcript_segments(
        {
            "segments": [
                {"start_ms": 0, "end_ms": 900, "text": "locked overlap"},
                {"start_ms": 1400, "end_ms": 2600, "text": "new line"},
            ]
        },
        project_id="proj_123",
        source_language="en-US",
        locked_segments=[
            {
                "segment_id": "seg_0001",
                "start_ms": 0,
                "end_ms": 1000,
                "source_text": "human edit",
                "locked": True,
            }
        ],
        locked_segment_ids=["seg_0001"],
        options=NormalizeOptions(max_merge_gap_ms=0),
    )

    assert [segment["source_text"] for segment in result["segments"]] == ["new line"]
    assert result["segments"][0]["segment_id"] == "seg_0002"
    assert result["skipped_locked_segment_ids"] == ["seg_0001"]
    assert "seg_0001" not in [segment["segment_id"] for segment in result["segments"]]
