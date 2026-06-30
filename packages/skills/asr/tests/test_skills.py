from __future__ import annotations

import json

from asr_skill import ASRSkillRunner, MockASRAdapter


def test_transcribe_uses_mock_adapter_and_writes_asr_json(tmp_path) -> None:
    runner = ASRSkillRunner(
        adapter=MockASRAdapter(
            detected_language="en-US",
            segments=[
                {"start_ms": 1000, "end_ms": 2200, "text": "Hello", "confidence": 0.91},
            ],
            speaker_timeline=[
                {"start_ms": 1000, "end_ms": 2200, "speaker": "SPEAKER_00"},
            ],
        )
    )
    request = {
        "skill_name": "asr.transcribe",
        "skill_version": "1.0.0",
        "project_id": "proj_123",
        "run_id": "run_123",
        "input": {
            "source_vocal": {"asset_id": "asset_vocals", "uri": "storage://private/projects/proj_123/v.wav"},
            "source_language": "auto",
            "enable_diarization": True,
        },
        "config": {"storage_root": str(tmp_path)},
        "idempotency_key": "run_123:asr.transcribe",
    }

    response = runner.invoke(request)

    assert response["status"] == "succeeded"
    assert response["error"] is None
    assert response["outputs"]["detected_language"] == "en-US"
    assert response["outputs"]["asr_json_path"] == "projects/proj_123/asr/source_segments.json"
    written = tmp_path / "projects/proj_123/asr/source_segments.json"
    assert written.exists()
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["raw_segments"][0]["text"] == "Hello"
    assert response["usage"] == {"provider": "mock", "model": "mock-asr"}


def test_diarize_accepts_transcript_and_maps_speakers() -> None:
    runner = ASRSkillRunner(adapter=MockASRAdapter())
    request = {
        "skill_name": "asr.diarize",
        "skill_version": "1.0.0",
        "project_id": "proj_123",
        "run_id": "run_123",
        "input": {
            "transcript": {
                "segments": [
                    {"start_ms": 0, "end_ms": 1000, "text": "A", "speaker": "SPEAKER_00"},
                    {"start_ms": 1000, "end_ms": 2000, "text": "B", "speaker": "SPEAKER_01"},
                ]
            }
        },
        "config": {},
        "idempotency_key": "run_123:asr.diarize",
    }

    response = runner.invoke(request)

    assert response["status"] == "succeeded"
    assert [turn["speaker_id"] for turn in response["outputs"]["speaker_timeline"]] == ["spk_1", "spk_2"]
    assert [speaker["speaker_id"] for speaker in response["outputs"]["speakers"]] == ["spk_1", "spk_2"]


def test_normalize_segments_skill_does_not_emit_locked_segment_ids(tmp_path) -> None:
    runner = ASRSkillRunner()
    request = {
        "skill_name": "transcript.normalize_segments",
        "skill_version": "1.0.0",
        "project_id": "proj_123",
        "run_id": "run_123",
        "input": {
            "source_language": "en-US",
            "raw_transcript": {
                "segments": [
                    {"start_ms": 0, "end_ms": 900, "text": "locked overlap"},
                    {"start_ms": 1500, "end_ms": 2500, "text": "new line"},
                ]
            },
            "locked_segments": [
                {
                    "segment_id": "seg_0001",
                    "start_ms": 0,
                    "end_ms": 1000,
                    "source_text": "edited",
                    "locked": True,
                }
            ],
            "locked_segment_ids": ["seg_0001"],
        },
        "config": {"storage_root": str(tmp_path), "max_merge_gap_ms": 0},
        "idempotency_key": "run_123:transcript.normalize_segments",
    }

    response = runner.invoke(request)

    assert response["status"] == "succeeded"
    assert response["outputs"]["segment_ids"] == ["seg_0002"]
    assert response["outputs"]["updated_segment_ids"] == ["seg_0002"]
    assert response["outputs"]["skipped_locked_segment_ids"] == ["seg_0001"]
    assert "seg_0001" not in response["outputs"]["updated_segment_ids"]


def test_asr_failed_error_response_from_adapter() -> None:
    runner = ASRSkillRunner(adapter=MockASRAdapter(fail=True, failure_message="model unavailable"))
    request = {
        "skill_name": "asr.transcribe",
        "skill_version": "1.0.0",
        "project_id": "proj_123",
        "run_id": "run_123",
        "input": {
            "source_vocal": "asset_vocals",
            "source_language": "zh-CN",
            "enable_diarization": False,
        },
        "config": {},
        "idempotency_key": "run_123:asr.transcribe",
    }

    response = runner.invoke(request)

    assert response["status"] == "failed"
    assert response["error"] == {"code": "ASR_FAILED", "message": "model unavailable"}
