from __future__ import annotations

from io import BytesIO
from pathlib import Path
import wave

import pytest

from voice_skill import (
    MockTTSAdapter,
    StepTTSAdapter,
    TTSAdapterError,
    TTSRequest,
    VoiceSkillRunner,
    adapter_from_config,
    select_voice_id,
    tts_segment_path,
)


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


def test_adapter_from_config_prefers_tts_provider_for_composite_config() -> None:
    adapter = adapter_from_config(
        {
            "provider": "deepseek",
            "api_key": "deepseek-key",
            "model": "deepseek-chat",
            "tts_provider": "step",
            "step_api_key": "step-key",
            "step_base_url": "https://step.example/v1",
            "step_tts_model": "step-model",
        }
    )

    assert isinstance(adapter, StepTTSAdapter)
    assert adapter.api_key == "step-key"
    assert adapter.base_url == "https://step.example/v1"
    assert adapter.model == "step-model"


def test_adapter_from_config_defaults_to_step_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STEP_API_KEY", "env-step-key")
    monkeypatch.setenv("STEP_BASE_URL", "https://env-step.example/v1")
    monkeypatch.setenv("STEP_TTS_MODEL", "env-step-model")

    adapter = adapter_from_config({})

    assert isinstance(adapter, StepTTSAdapter)
    assert adapter.api_key == "env-step-key"
    assert adapter.base_url == "https://env-step.example/v1"
    assert adapter.model == "env-step-model"


def test_step_tts_adapter_calls_openai_speech_create() -> None:
    audio = _silent_wav(1234)
    speech = _FakeSpeech(audio)
    client = _FakeOpenAIClient(speech)
    adapter = StepTTSAdapter(
        api_key="step-key",
        base_url="https://step.example/v1",
        model="stepaudio-test",
        instruction="dramatic delivery",
        client=client,
    )

    result = adapter.synthesize(
        TTSRequest(
            target_language="en-US",
            text="What exactly do you want from me?",
            voice_id="linjiajiejie",
            target_duration_ms=2400,
            speed=1.0,
            style=None,
            segment_id="seg_0001",
        )
    )

    assert result.audio == audio
    assert result.actual_duration_ms == 1234
    assert result.provider == "step"
    assert result.provider_task_id == "req_step_123"
    assert speech.calls == [
        {
            "model": "stepaudio-test",
            "input": "What exactly do you want from me?",
            "voice": "linjiajiejie",
            "extra_body": {"instruction": "dramatic delivery"},
            "timeout": 60,
        }
    ]


def test_step_tts_adapter_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STEP_API_KEY", raising=False)
    adapter = StepTTSAdapter(api_key="", client=_FakeOpenAIClient(_FakeSpeech(_silent_wav(1000))))

    with pytest.raises(TTSAdapterError) as exc_info:
        adapter.synthesize(
            TTSRequest(
                target_language="en-US",
                text="Hello",
                voice_id="cixingnansheng",
                target_duration_ms=1000,
            )
        )

    assert exc_info.value.code == "PROVIDER_UNAVAILABLE"
    assert "Missing Step API key" in str(exc_info.value)


def test_step_tts_adapter_maps_rate_limit_error() -> None:
    import httpx
    from openai import RateLimitError

    request = httpx.Request("POST", "https://step.example/v1/audio/speech")
    response = httpx.Response(429, request=request)
    adapter = StepTTSAdapter(
        api_key="step-key",
        client=_FakeOpenAIClient(_FailingSpeech(RateLimitError("rate limited", response=response, body=None))),
    )

    with pytest.raises(TTSAdapterError) as exc_info:
        adapter.synthesize(
            TTSRequest(
                target_language="en-US",
                text="Hello",
                voice_id="cixingnansheng",
                target_duration_ms=1000,
            )
        )

    assert exc_info.value.code == "PROVIDER_RATE_LIMITED"


def test_step_tts_adapter_maps_timeout_error() -> None:
    import httpx
    from openai import APITimeoutError

    request = httpx.Request("POST", "https://step.example/v1/audio/speech")
    adapter = StepTTSAdapter(
        api_key="step-key",
        client=_FakeOpenAIClient(_FailingSpeech(APITimeoutError(request=request))),
    )

    with pytest.raises(TTSAdapterError) as exc_info:
        adapter.synthesize(
            TTSRequest(
                target_language="en-US",
                text="Hello",
                voice_id="cixingnansheng",
                target_duration_ms=1000,
            )
        )

    assert exc_info.value.code == "PROVIDER_UNAVAILABLE"
    assert "timed out" in str(exc_info.value)


def test_step_default_voice_uses_builtin_voice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STEP_TTS_VOICE_ID", raising=False)
    monkeypatch.delenv("STEP_TTS_DEFAULT_VOICE_ID", raising=False)
    monkeypatch.delenv("STEP_DEFAULT_VOICE_ID", raising=False)

    voice_id = select_voice_id(
        segment={"segment_id": "seg_0001"},
        translation=None,
        speakers={},
        payload={},
        config={"tts_provider": "step"},
        target_language="en-US",
    )

    assert voice_id == "cixingnansheng"


def test_step_default_voice_can_use_builtin_voice_from_config() -> None:
    voice_id = select_voice_id(
        segment={"segment_id": "seg_0001"},
        translation=None,
        speakers={},
        payload={},
        config={"tts_provider": "step", "step_tts_voice_id": "linjiajiejie"},
        target_language="en-US",
    )

    assert voice_id == "linjiajiejie"


class _FakeOpenAIClient:
    def __init__(self, speech: "_FakeSpeech") -> None:
        self.audio = type("Audio", (), {"speech": speech})()


class _FakeSpeech:
    def __init__(self, audio: bytes) -> None:
        self.audio = audio
        self.calls: list[dict] = []

    def create(self, **kwargs: object) -> "_FakeSpeechResponse":
        self.calls.append(dict(kwargs))
        return _FakeSpeechResponse(self.audio)


class _FailingSpeech:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def create(self, **_kwargs: object) -> "_FakeSpeechResponse":
        raise self.exc


class _FakeSpeechResponse:
    response = type("Response", (), {"headers": {"x-request-id": "req_step_123"}})()

    def __init__(self, audio: bytes) -> None:
        self.audio = audio

    def write_to_file(self, output_path: str | Path) -> None:
        Path(output_path).write_bytes(self.audio)


def _silent_wav(duration_ms: int, *, sample_rate: int = 16_000) -> bytes:
    sample_count = int(sample_rate * duration_ms / 1000)
    buffer = BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * sample_count)
    return buffer.getvalue()
