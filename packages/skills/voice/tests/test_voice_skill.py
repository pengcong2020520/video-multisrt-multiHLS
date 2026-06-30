from __future__ import annotations

from pathlib import Path

from voice_skill import MockTTSAdapter, VoiceSkillRunner, tts_segment_path


def _request(
    *,
    segments: list[dict],
    translations: list[dict],
    speakers: list[dict] | None = None,
    input_extra: dict | None = None,
    config: dict | None = None,
) -> dict:
    payload = {
        "target_language": "en-US",
        "segments": segments,
        "translations": translations,
        "speakers": speakers or [
            {
                "speaker_id": "spk_1",
                "project_id": "proj_123",
                "display_name": "Female Lead",
                "source_voice_sample_asset_id": None,
                "target_voice_map": {"en-US": "voice_en_female_01"},
            }
        ],
    }
    if input_extra:
        payload.update(input_extra)
    return {
        "skill_name": "voice.synthesize",
        "skill_version": "1.0.0",
        "project_id": "proj_123",
        "run_id": "run_123",
        "input": payload,
        "config": config or {},
        "idempotency_key": "run_123:voice.synthesize:en-US:v1",
    }


def _segment(segment_id: str = "seg_0001", *, start_ms: int = 1200, end_ms: int = 3600, speaker_id: str = "spk_1") -> dict:
    return {
        "segment_id": segment_id,
        "project_id": "proj_123",
        "index": 1,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "speaker_id": speaker_id,
        "source_language": "zh-CN",
        "source_text": "你到底想怎么样？",
        "asr_confidence": 0.92,
        "locked": False,
        "quality_flags": [],
    }


def _translation(segment_id: str = "seg_0001", text: str = "What exactly do you want from me?") -> dict:
    return {
        "translation_id": f"tr_{segment_id}_en",
        "segment_id": segment_id,
        "target_language": "en-US",
        "text": text,
        "style": "short_drama_localized",
        "status": "completed",
        "edited_by": None,
        "updated_at": "2026-06-30T10:05:00Z",
        "active": True,
    }


def test_segment_duration_maps_to_target_duration_and_spec_path(tmp_path: Path) -> None:
    runner = VoiceSkillRunner(adapter=MockTTSAdapter())

    response = runner.invoke(
        _request(
            segments=[_segment(start_ms=1200, end_ms=3600)],
            translations=[_translation()],
            config={"storage_root": str(tmp_path)},
        )
    )

    assert response["status"] == "succeeded"
    job = response["outputs"]["tts_jobs"][0]
    assert job["target_duration_ms"] == 2400
    assert job["actual_duration_ms"] == 2400
    assert response["assets"][0]["storage_key"] == "projects/proj_123/tts/en-US/seg_0001.wav"
    assert (tmp_path / tts_segment_path("proj_123", "en-US", "seg_0001")).exists()


def test_speaker_id_maps_to_target_language_voice_id(tmp_path: Path) -> None:
    runner = VoiceSkillRunner(adapter=MockTTSAdapter())
    speakers = [
        {
            "speaker_id": "spk_2",
            "project_id": "proj_123",
            "display_name": "Male Lead",
            "source_voice_sample_asset_id": None,
            "target_voice_map": {"en-US": "voice_en_male_02", "es-ES": "voice_es_male_02"},
        }
    ]

    response = runner.invoke(
        _request(
            segments=[_segment(speaker_id="spk_2")],
            translations=[_translation()],
            speakers=speakers,
            config={"storage_root": str(tmp_path)},
        )
    )

    assert response["status"] == "succeeded"
    assert response["outputs"]["tts_jobs"][0]["voice_id"] == "voice_en_male_02"


def test_duration_drift_over_20_percent_adds_quality_flag(tmp_path: Path) -> None:
    runner = VoiceSkillRunner(adapter=MockTTSAdapter(actual_duration_ms_by_segment={"seg_0001": 3100}))

    response = runner.invoke(
        _request(
            segments=[_segment(start_ms=1200, end_ms=3600)],
            translations=[_translation()],
            config={"storage_root": str(tmp_path)},
        )
    )

    assert response["status"] == "succeeded"
    assert response["outputs"]["tts_jobs"][0]["actual_duration_ms"] == 3100
    assert response["quality_flags"] == [
        {
            "code": "duration_drift",
            "message": "TTS duration differs from target by more than 20%",
            "severity": "warning",
            "segment_id": "seg_0001",
            "language": "en-US",
        }
    ]
    assert response["outputs"]["tts_jobs"][0]["quality_flags"] == response["quality_flags"]


def test_provider_failure_maps_to_structured_error_and_failed_tts_job(tmp_path: Path) -> None:
    runner = VoiceSkillRunner(
        adapter=MockTTSAdapter(
            fail=True,
            failure_code="PROVIDER_RATE_LIMITED",
            failure_message="provider throttled",
        )
    )

    response = runner.invoke(
        _request(
            segments=[_segment()],
            translations=[_translation()],
            config={"storage_root": str(tmp_path)},
        )
    )

    assert response["status"] == "failed"
    assert response["error"] == {"code": "PROVIDER_RATE_LIMITED", "message": "provider throttled"}
    assert response["assets"] == []
    job = response["outputs"]["tts_jobs"][0]
    assert job["status"] == "failed"
    assert job["error"] == response["error"]
    assert job["provider"] == "mock"


def test_single_segment_rerun_generates_only_selected_segment(tmp_path: Path) -> None:
    runner = VoiceSkillRunner(adapter=MockTTSAdapter())
    segments = [
        _segment("seg_0001", start_ms=0, end_ms=1000),
        _segment("seg_0002", start_ms=1000, end_ms=2200),
    ]
    translations = [_translation("seg_0001", "First line"), _translation("seg_0002", "Second line")]

    response = runner.invoke(
        _request(
            segments=segments,
            translations=translations,
            input_extra={"scope": "segments", "segment_ids": ["seg_0002"]},
            config={"storage_root": str(tmp_path)},
        )
    )

    assert response["status"] == "succeeded"
    assert response["outputs"]["segment_ids"] == ["seg_0002"]
    assert response["outputs"]["tts_jobs"][0]["text"] == "Second line"
    assert (tmp_path / tts_segment_path("proj_123", "en-US", "seg_0002")).exists()
    assert not (tmp_path / tts_segment_path("proj_123", "en-US", "seg_0001")).exists()


def test_unauthorized_voice_clone_request_is_rejected() -> None:
    runner = VoiceSkillRunner(adapter=MockTTSAdapter())

    response = runner.invoke(
        _request(
            segments=[_segment()],
            translations=[_translation()],
            input_extra={"enable_voice_clone": True},
        )
    )

    assert response["status"] == "failed"
    assert response["error"]["code"] == "SKILL_RUN_FAILED"
