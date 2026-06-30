from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from typing import Any, Protocol
from urllib import error as urlerror
from urllib import request as urlrequest

from localization_skill.prompts import DEFAULT_PROMPT_VERSION, build_translation_messages


ERROR_CODES = {
    "TRANSLATION_FAILED",
    "PROVIDER_RATE_LIMITED",
    "PROVIDER_UNAVAILABLE",
}


class TranslationAdapterError(RuntimeError):
    def __init__(self, message: str, *, code: str = "TRANSLATION_FAILED") -> None:
        super().__init__(message)
        self.code = code if code in ERROR_CODES else "TRANSLATION_FAILED"


@dataclass(frozen=True)
class TranslationRequest:
    source_language: str
    target_language: str
    segments: list[dict[str, Any]]
    style: str = "short_drama_localized"
    glossary: dict[str, str] = field(default_factory=dict)
    character_notes: list[str] = field(default_factory=list)
    forbidden_terms: list[str] = field(default_factory=list)
    length_policy: Any = "match_duration"


@dataclass(frozen=True)
class TranslationCandidate:
    segment_id: str
    text: str
    quality_flags: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "text": self.text,
            "quality_flags": list(self.quality_flags),
        }


@dataclass(frozen=True)
class TranslationResult:
    translations: list[TranslationCandidate]
    provider: str
    model: str
    prompt_version: str
    usage: dict[str, Any] = field(default_factory=dict)


class TranslationAdapterPort(Protocol):
    provider: str
    model: str
    prompt_version: str

    def translate(self, request: TranslationRequest) -> TranslationResult:
        ...


class JsonHttpClient(Protocol):
    def post_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        ...


class UrllibJsonHttpClient:
    def post_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urlrequest.Request(
            url,
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with urlrequest.urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except urlerror.HTTPError as exc:  # pragma: no cover - real provider boundary
            body = exc.read().decode("utf-8", errors="replace")
            raise TranslationAdapterError(
                _provider_error_message(body) or f"Provider HTTP {exc.code}",
                code=_error_code_for_status(exc.code),
            ) from exc
        except urlerror.URLError as exc:  # pragma: no cover - real provider boundary
            raise TranslationAdapterError(
                f"Provider unavailable: {exc.reason}",
                code="PROVIDER_UNAVAILABLE",
            ) from exc
        except TimeoutError as exc:  # pragma: no cover - real provider boundary
            raise TranslationAdapterError("Provider request timed out", code="PROVIDER_UNAVAILABLE") from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:  # pragma: no cover - real provider boundary
            raise TranslationAdapterError("Provider returned invalid JSON") from exc


class DeepSeekTranslationAdapter:
    provider = "deepseek"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
        prompt_version: str = DEFAULT_PROMPT_VERSION,
        timeout_seconds: float = 60.0,
        temperature: float = 0.3,
        http_client: JsonHttpClient | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.prompt_version = prompt_version
        self.timeout_seconds = timeout_seconds
        self.temperature = temperature
        self.http_client = http_client or UrllibJsonHttpClient()

    def translate(self, request: TranslationRequest) -> TranslationResult:
        if not self.api_key:
            raise TranslationAdapterError("Missing DeepSeek API key", code="PROVIDER_UNAVAILABLE")

        messages = build_translation_messages(
            source_language=request.source_language,
            target_language=request.target_language,
            segments=request.segments,
            style=request.style,
            glossary=request.glossary,
            character_notes=request.character_notes,
            forbidden_terms=request.forbidden_terms,
            length_policy=request.length_policy,
            prompt_version=self.prompt_version,
        )
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = self.http_client.post_json(
                f"{self.base_url}/chat/completions",
                headers=headers,
                payload=payload,
                timeout_seconds=self.timeout_seconds,
            )
        except TranslationAdapterError:
            raise
        except Exception as exc:  # pragma: no cover - provider boundary
            raise TranslationAdapterError("Provider request failed") from exc

        return self._parse_chat_completion(response)

    def _parse_chat_completion(self, response: dict[str, Any]) -> TranslationResult:
        try:
            choice = response["choices"][0]
            message = choice["message"]
            content = message["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TranslationAdapterError("Provider response is missing chat content") from exc

        content_payload = _parse_json_content(content)
        translations = [
            _candidate_from_mapping(item)
            for item in content_payload.get("translations", [])
            if isinstance(item, dict)
        ]
        if not translations and content_payload.get("translations") != []:
            raise TranslationAdapterError("Provider response has invalid translations")

        usage_payload = response.get("usage") if isinstance(response.get("usage"), dict) else {}
        usage = {
            "tokens": _int_or_zero(usage_payload.get("total_tokens")),
            "prompt_tokens": _int_or_zero(usage_payload.get("prompt_tokens")),
            "completion_tokens": _int_or_zero(usage_payload.get("completion_tokens")),
            "cost": None,
        }
        return TranslationResult(
            translations=translations,
            provider=self.provider,
            model=str(response.get("model") or self.model),
            prompt_version=self.prompt_version,
            usage=usage,
        )


class MockTranslationAdapter:
    provider = "mock"

    def __init__(
        self,
        *,
        translations: dict[str, str | dict[str, Any]] | list[dict[str, Any]] | None = None,
        model: str = "mock-translation",
        prompt_version: str = DEFAULT_PROMPT_VERSION,
        fail: bool = False,
        failure_code: str = "TRANSLATION_FAILED",
        failure_message: str = "Mock translation failed",
        usage: dict[str, Any] | None = None,
    ) -> None:
        self.model = model
        self.prompt_version = prompt_version
        self.fail = fail
        self.failure_code = failure_code
        self.failure_message = failure_message
        self.usage = usage or {"tokens": 0, "cost": None}
        self.requests: list[TranslationRequest] = []
        self._translations = _normalize_mock_translations(translations)

    def translate(self, request: TranslationRequest) -> TranslationResult:
        self.requests.append(request)
        if self.fail:
            raise TranslationAdapterError(self.failure_message, code=self.failure_code)

        translations: list[TranslationCandidate] = []
        for segment in request.segments:
            segment_id = str(segment.get("segment_id") or "")
            configured = self._translations.get(segment_id)
            if configured is None:
                text = f"[{request.target_language}] {segment.get('source_text') or ''}".strip()
                translations.append(TranslationCandidate(segment_id=segment_id, text=text, quality_flags=[]))
            else:
                translations.append(configured)
        return TranslationResult(
            translations=translations,
            provider=self.provider,
            model=self.model,
            prompt_version=self.prompt_version,
            usage=dict(self.usage),
        )


def adapter_from_config(
    config: dict[str, Any] | None = None,
    *,
    http_client: JsonHttpClient | None = None,
) -> TranslationAdapterPort:
    config = config or {}
    provider = str(config.get("provider") or config.get("translation_provider") or "deepseek").lower()
    if provider == "mock":
        return MockTranslationAdapter(
            translations=config.get("mock_translations") or config.get("translations"),
            model=str(config.get("model") or config.get("translation_model") or "mock-translation"),
            prompt_version=str(config.get("prompt_version") or DEFAULT_PROMPT_VERSION),
            fail=bool(config.get("fail")),
            failure_code=str(config.get("failure_code") or "TRANSLATION_FAILED"),
            failure_message=str(config.get("failure_message") or "Mock translation failed"),
        )
    if provider in {"deepseek", "openai-compatible", "openai_compatible"}:
        return DeepSeekTranslationAdapter(
            api_key=config.get("api_key") or config.get("deepseek_api_key"),
            base_url=str(config.get("base_url") or config.get("deepseek_base_url") or "https://api.deepseek.com/v1"),
            model=str(config.get("model") or config.get("translation_model") or "deepseek-chat"),
            prompt_version=str(config.get("prompt_version") or DEFAULT_PROMPT_VERSION),
            timeout_seconds=float(config.get("timeout_seconds") or 60.0),
            temperature=float(config.get("temperature") or 0.3),
            http_client=http_client,
        )
    raise TranslationAdapterError(f"Unsupported translation provider: {provider}", code="PROVIDER_UNAVAILABLE")


def provider_metadata_from_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or {}
    provider = str(config.get("provider") or config.get("translation_provider") or "deepseek")
    model = str(config.get("model") or config.get("translation_model") or "deepseek-chat")
    prompt_version = str(config.get("prompt_version") or DEFAULT_PROMPT_VERSION)
    return {"provider": provider, "model": model, "prompt_version": prompt_version}


def _parse_json_content(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        raise TranslationAdapterError("Provider response content is not text")
    text = content.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise TranslationAdapterError("Provider response content is not JSON")
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise TranslationAdapterError("Provider response content is not JSON") from exc
    if not isinstance(parsed, dict):
        raise TranslationAdapterError("Provider response JSON must be an object")
    return parsed


def _candidate_from_mapping(value: dict[str, Any]) -> TranslationCandidate:
    segment_id = str(value.get("segment_id") or "")
    if not segment_id:
        raise TranslationAdapterError("Translation item is missing segment_id")
    quality_flags = value.get("quality_flags")
    return TranslationCandidate(
        segment_id=segment_id,
        text=str(value.get("text") or ""),
        quality_flags=[dict(flag) for flag in quality_flags if isinstance(flag, dict)]
        if isinstance(quality_flags, list)
        else [],
    )


def _normalize_mock_translations(
    value: dict[str, str | dict[str, Any]] | list[dict[str, Any]] | None,
) -> dict[str, TranslationCandidate]:
    if value is None:
        return {}
    if isinstance(value, list):
        return {
            candidate.segment_id: candidate
            for candidate in (_candidate_from_mapping(item) for item in value if isinstance(item, dict))
        }
    normalized: dict[str, TranslationCandidate] = {}
    for segment_id, item in value.items():
        if isinstance(item, dict):
            payload = dict(item)
            payload.setdefault("segment_id", segment_id)
            normalized[str(segment_id)] = _candidate_from_mapping(payload)
        else:
            normalized[str(segment_id)] = TranslationCandidate(str(segment_id), str(item), [])
    return normalized


def _provider_error_message(body: str) -> str | None:
    if not body:
        return None
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return body.strip() or None
    error = payload.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("code") or "").strip() or None
    return str(payload.get("message") or "").strip() or None


def _error_code_for_status(status: int) -> str:
    if status == 429:
        return "PROVIDER_RATE_LIMITED"
    if status in {500, 502, 503, 504}:
        return "PROVIDER_UNAVAILABLE"
    return "TRANSLATION_FAILED"


def _int_or_zero(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0
