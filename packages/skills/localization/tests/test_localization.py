from __future__ import annotations

import json
from pathlib import Path

import pytest

from localization_skill import (
    DeepSeekTranslationAdapter,
    LocalizationSkillRunner,
    MockTranslationAdapter,
    TranslationRequest,
    translation_json_path,
)


def _request(payload: dict, *, config: dict | None = None) -> dict:
    return {
        "skill_name": "localization.translate",
        "skill_version": "1.0.0",
        "project_id": "proj_123",
        "run_id": "run_123",
        "input": payload,
        "config": config or {},
        "idempotency_key": "run_123:localization.translate:en-US:v1",
    }


def _segment(
    segment_id: str,
    source_text: str = "\u4f60\u5230\u5e95\u60f3\u600e\u6837\uff1f",
    *,
    index: int = 1,
    locked: bool = False,
) -> dict:
    return {
        "segment_id": segment_id,
        "project_id": "proj_123",
        "index": index,
        "start_ms": 1000 * index,
        "end_ms": 1000 * index + 1800,
        "speaker_id": "spk_1",
        "source_language": "zh-CN",
        "source_text": source_text,
        "asr_confidence": 0.92,
        "locked": locked,
        "quality_flags": [],
    }


class FakeHttpClient:
    def __init__(self, response: dict) -> None:
        self.response = response
        self.calls: list[dict] = []

    def post_json(self, url: str, *, headers: dict, payload: dict, timeout_seconds: float) -> dict:
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "payload": payload,
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.response


def test_deepseek_adapter_maps_openai_compatible_request_and_response() -> None:
    fake_http = FakeHttpClient(
        {
            "model": "deepseek-chat",
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "translations": [
                                    {
                                        "segment_id": "seg_0001",
                                        "text": "What exactly do you want from me?",
                                        "quality_flags": [],
                                    }
                                ]
                            }
                        )
                    }
                }
            ],
            "usage": {"prompt_tokens": 80, "completion_tokens": 20, "total_tokens": 100},
        }
    )
    adapter = DeepSeekTranslationAdapter(
        api_key="sk-test",
        base_url="https://api.deepseek.test/v1",
        model="deepseek-chat",
        prompt_version="short_drama_v1",
        http_client=fake_http,
    )

    result = adapter.translate(
        TranslationRequest(
            source_language="zh-CN",
            target_language="en-US",
            segments=[_segment("seg_0001")],
            style="short_drama_localized",
            glossary={"\u987e\u603b": "Mr. Gu"},
            character_notes=["The female lead is furious but controlled."],
            forbidden_terms=["jerk"],
            length_policy={"max_chars": 48},
        )
    )

    assert result.provider == "deepseek"
    assert result.model == "deepseek-chat"
    assert result.prompt_version == "short_drama_v1"
    assert result.usage["tokens"] == 100
    assert result.translations[0].to_dict() == {
        "segment_id": "seg_0001",
        "text": "What exactly do you want from me?",
        "quality_flags": [],
    }
    call = fake_http.calls[0]
    assert call["url"] == "https://api.deepseek.test/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer sk-test"
    assert call["payload"]["model"] == "deepseek-chat"
    assert call["payload"]["response_format"] == {"type": "json_object"}
    user_prompt = call["payload"]["messages"][1]["content"]
    assert "short_drama_localized" in user_prompt
    assert "Mr. Gu" in user_prompt
    assert "forbidden_terms" in user_prompt


def test_translate_switches_active_version_and_writes_translation_json(tmp_path: Path) -> None:
    runner = LocalizationSkillRunner(
        adapter=MockTranslationAdapter(translations={"seg_0001": "What exactly do you want?"}, usage={"tokens": 42})
    )
    existing = [
        {
            "translation_id": "tr_old_en",
            "segment_id": "seg_0001",
            "target_language": "en-US",
            "text": "Old text",
            "style": "short_drama_localized",
            "model": "deepseek-chat",
            "prompt_version": "short_drama_v0",
            "status": "completed",
            "edited_by": None,
            "updated_at": "2026-06-30T10:00:00Z",
            "active": True,
        }
    ]

    response = runner.invoke(
        _request(
            {
                "source_language": "zh-CN",
                "target_language": "en-US",
                "segments": [_segment("seg_0001")],
                "style": "short_drama_localized",
                "existing_translations": existing,
                "length_policy": "loose",
            },
            config={"storage_root": str(tmp_path), "now": "2026-06-30T10:05:00Z"},
        )
    )

    assert response["status"] == "succeeded"
    assert response["outputs"]["translation_json_path"] == translation_json_path("proj_123", "en-US")
    assert response["outputs"]["deactivated_translation_ids"] == ["tr_old_en"]
    assert response["outputs"]["translations"][0]["text"] == "What exactly do you want?"
    assert response["outputs"]["translations"][0]["active"] is True
    old_versions = [
        item
        for item in response["outputs"]["translation_versions"]
        if item["translation_id"] == "tr_old_en"
    ]
    assert old_versions[0]["active"] is False
    assert response["usage"] == {"provider": "mock", "model": "mock-translation", "tokens": 42, "cost": None}

    written = tmp_path / "projects/proj_123/translations/en-US.json"
    assert written.exists()
    payload = json.loads(written.read_text(encoding="utf-8"))
    assert payload["translations"][0]["text"] == "What exactly do you want?"
    assert payload["translation_versions"][0]["translation_id"] == "tr_old_en"


def test_locked_segment_preserves_existing_active_translation_and_skips_provider(tmp_path: Path) -> None:
    adapter = MockTranslationAdapter(translations={"seg_0001": "AI should not replace this"})
    runner = LocalizationSkillRunner(adapter=adapter)

    response = runner.invoke(
        _request(
            {
                "source_language": "zh-CN",
                "target_language": "en-US",
                "segments": [_segment("seg_0001", locked=True)],
                "style": "short_drama_localized",
                "existing_translations": [
                    {
                        "translation_id": "tr_manual_en",
                        "segment_id": "seg_0001",
                        "target_language": "en-US",
                        "text": "Manual approved line.",
                        "style": "short_drama_localized",
                        "model": "human",
                        "prompt_version": "manual",
                        "status": "completed",
                        "edited_by": "user_001",
                        "updated_at": "2026-06-30T10:01:00Z",
                        "active": True,
                    }
                ],
            },
            config={"storage_root": str(tmp_path)},
        )
    )

    assert response["status"] == "succeeded"
    assert adapter.requests == []
    assert response["outputs"]["updated_translation_ids"] == []
    assert response["outputs"]["skipped_locked_segment_ids"] == ["seg_0001"]
    assert response["outputs"]["translations"][0]["translation_id"] == "tr_manual_en"
    assert response["outputs"]["translations"][0]["text"] == "Manual approved line."
    assert response["outputs"]["translations"][0]["active"] is True


def test_quality_flags_include_empty_too_long_and_target_language_missing() -> None:
    runner = LocalizationSkillRunner(
        adapter=MockTranslationAdapter(
            translations={
                "seg_empty": "",
                "seg_long": "This localized line is much too long for the tiny timing window.",
                "seg_wrong_language": "\u8fd9\u8fd8\u662f\u4e2d\u6587",
            }
        )
    )

    response = runner.invoke(
        _request(
            {
                "source_language": "zh-CN",
                "target_language": "en-US",
                "segments": [
                    _segment("seg_empty", index=1),
                    _segment("seg_long", index=2),
                    _segment("seg_wrong_language", index=3),
                ],
                "style": "short_drama_localized",
                "length_policy": {"max_chars": 12},
            }
        )
    )

    assert response["status"] == "succeeded"
    codes = {flag["code"] for flag in response["quality_flags"]}
    assert "empty_translation" in codes
    assert "translation_too_long" in codes
    assert "target_language_missing" in codes
    by_segment = {
        (flag.get("segment_id"), flag["code"])
        for flag in response["outputs"]["translations"][0]["quality_flags"]
    }
    assert ("seg_empty", "empty_translation") in by_segment


@pytest.mark.parametrize("failure_code", ["PROVIDER_RATE_LIMITED", "PROVIDER_UNAVAILABLE", "TRANSLATION_FAILED"])
def test_provider_failure_maps_to_spec_error_codes(failure_code: str) -> None:
    runner = LocalizationSkillRunner(
        adapter=MockTranslationAdapter(fail=True, failure_code=failure_code, failure_message="provider failed")
    )

    response = runner.invoke(
        _request(
            {
                "source_language": "zh-CN",
                "target_language": "en-US",
                "segments": [_segment("seg_0001")],
                "style": "short_drama_localized",
            }
        )
    )

    assert response["status"] == "failed"
    assert response["error"] == {"code": failure_code, "message": "provider failed"}
    assert response["usage"] == {}
