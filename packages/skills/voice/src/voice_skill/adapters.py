from __future__ import annotations

import base64
import json
import os
import tempfile
import wave
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request as HttpRequest
from urllib.request import urlopen


class TTSAdapterError(RuntimeError):
    def __init__(self, message: str, *, code: str = "TTS_FAILED") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class TTSRequest:
    target_language: str
    text: str
    voice_id: str
    target_duration_ms: int | None
    speed: float = 1.0
    style: str | None = None
    segment_id: str | None = None


@dataclass(frozen=True)
class TTSResult:
    audio: bytes
    actual_duration_ms: int
    provider: str
    provider_task_id: str
    model: str | None = None


class TTSAdapterPort(Protocol):
    provider: str
    model: str | None

    def synthesize(self, request: TTSRequest) -> TTSResult:
        ...


class MockTTSAdapter:
    provider = "mock"
    model = "mock-tts"

    def __init__(
        self,
        *,
        actual_duration_ms: int | None = None,
        actual_duration_ms_by_segment: dict[str, int] | None = None,
        fail: bool = False,
        fail_segment_ids: list[str] | set[str] | None = None,
        failure_code: str = "TTS_FAILED",
        failure_message: str = "Mock TTS failed",
        sample_rate: int = 16_000,
    ) -> None:
        self.actual_duration_ms = actual_duration_ms
        self.actual_duration_ms_by_segment = actual_duration_ms_by_segment or {}
        self.fail = fail
        self.fail_segment_ids = {str(item) for item in (fail_segment_ids or [])}
        self.failure_code = failure_code
        self.failure_message = failure_message
        self.sample_rate = sample_rate
        self.requests: list[TTSRequest] = []

    def synthesize(self, request: TTSRequest) -> TTSResult:
        self.requests.append(request)
        if self.fail or (request.segment_id and request.segment_id in self.fail_segment_ids):
            raise TTSAdapterError(self.failure_message, code=self.failure_code)

        actual_duration_ms = (
            self.actual_duration_ms_by_segment.get(str(request.segment_id))
            if request.segment_id is not None
            else None
        )
        if actual_duration_ms is None:
            actual_duration_ms = self.actual_duration_ms
        if actual_duration_ms is None:
            actual_duration_ms = request.target_duration_ms or _estimate_duration_ms(request.text)

        return TTSResult(
            audio=_silent_wav(actual_duration_ms, sample_rate=self.sample_rate),
            actual_duration_ms=actual_duration_ms,
            provider=self.provider,
            provider_task_id=f"mock_tts_{request.segment_id or len(self.requests)}",
            model=self.model,
        )


class MiniMaxTTSAdapter:
    provider = "minimax"

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 60,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model or "speech-02-hd"
        self.timeout_seconds = timeout_seconds

    def synthesize(self, request: TTSRequest) -> TTSResult:
        if not self.endpoint or not self.api_key:
            raise TTSAdapterError("MiniMax TTS endpoint and API key are required", code="PROVIDER_UNAVAILABLE")
        return _json_tts_request(
            provider=self.provider,
            endpoint=self.endpoint,
            api_key=self.api_key,
            model=self.model,
            timeout_seconds=self.timeout_seconds,
            request=request,
        )


class DoubaoTTSAdapter:
    provider = "doubao"

    def __init__(
        self,
        *,
        endpoint: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        app_id: str | None = None,
        timeout_seconds: float = 60,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = model or "doubao-tts"
        self.app_id = app_id
        self.timeout_seconds = timeout_seconds

    def synthesize(self, request: TTSRequest) -> TTSResult:
        if not self.endpoint or not self.api_key:
            raise TTSAdapterError("Doubao TTS endpoint and API key are required", code="PROVIDER_UNAVAILABLE")
        extra = {"app_id": self.app_id} if self.app_id else None
        return _json_tts_request(
            provider=self.provider,
            endpoint=self.endpoint,
            api_key=self.api_key,
            model=self.model,
            timeout_seconds=self.timeout_seconds,
            request=request,
            extra=extra,
        )


class StepTTSAdapter:
    provider = "step"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        instruction: str | None = None,
        timeout_seconds: float = 60,
        client: Any | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("STEP_API_KEY")
        self.base_url = (base_url or os.environ.get("STEP_BASE_URL") or "https://api.stepfun.com/step_plan/v1").rstrip(
            "/"
        )
        self.model = model or os.environ.get("STEP_TTS_MODEL") or "stepaudio-2.5-tts"
        self.instruction = instruction
        self.timeout_seconds = timeout_seconds
        self._client = client

    def synthesize(self, request: TTSRequest) -> TTSResult:
        if not self.api_key:
            raise TTSAdapterError("Missing Step API key", code="PROVIDER_UNAVAILABLE")

        client = self._client or self._openai_client()
        instruction = _step_instruction(self.instruction, request)
        output_path = _temporary_audio_path()
        try:
            response = client.audio.speech.create(
                model=self.model,
                input=request.text,
                voice=request.voice_id,
                extra_body={"instruction": instruction},
                timeout=self.timeout_seconds,
            )
            response.write_to_file(output_path)
            audio = output_path.read_bytes()
        except TTSAdapterError:
            raise
        except Exception as exc:
            raise _step_error(exc) from exc
        finally:
            output_path.unlink(missing_ok=True)

        if not audio:
            raise TTSAdapterError("Step TTS response did not include audio bytes")

        return TTSResult(
            audio=audio,
            actual_duration_ms=_audio_duration_ms(audio) or request.target_duration_ms or _estimate_duration_ms(request.text),
            provider=self.provider,
            provider_task_id=_step_provider_task_id(response, request),
            model=self.model,
        )

    def _openai_client(self) -> Any:
        try:
            from openai import OpenAI
        except Exception as exc:  # pragma: no cover - optional dependency boundary.
            raise TTSAdapterError("openai SDK is required for Step TTS", code="PROVIDER_UNAVAILABLE") from exc
        return OpenAI(api_key=self.api_key, base_url=self.base_url)


def adapter_from_config(config: dict[str, Any] | None = None) -> TTSAdapterPort:
    config = config or {}
    provider = _tts_provider(config)
    if provider == "mock":
        return MockTTSAdapter(
            actual_duration_ms=_int_or_none(config.get("mock_actual_duration_ms") or config.get("actual_duration_ms")),
            actual_duration_ms_by_segment={
                str(key): int(value)
                for key, value in (config.get("mock_actual_duration_ms_by_segment") or {}).items()
            },
            fail=bool(config.get("fail") or config.get("mock_fail")),
            fail_segment_ids=config.get("mock_fail_segment_ids") or [],
            failure_code=str(config.get("failure_code") or config.get("mock_failure_code") or "TTS_FAILED"),
            failure_message=str(config.get("failure_message") or config.get("mock_failure_message") or "Mock TTS failed"),
        )
    if provider in {"step", "stepfun", "step-tts", "step_tts"}:
        return StepTTSAdapter(
            api_key=_step_config_value(config, "step_api_key", "step_tts_api_key", "tts_api_key", generic_key="api_key"),
            base_url=_step_config_value(
                config,
                "step_base_url",
                "step_tts_base_url",
                "tts_base_url",
                generic_key="base_url",
            ),
            model=_step_config_value(config, "step_tts_model", "tts_model", generic_key="model"),
            instruction=_non_empty_str(config.get("step_tts_instruction") or config.get("tts_instruction")),
            timeout_seconds=float(config.get("timeout_seconds") or config.get("tts_timeout_seconds") or 60),
        )
    if provider == "minimax":
        return MiniMaxTTSAdapter(
            endpoint=config.get("endpoint") or config.get("tts_endpoint") or config.get("minimax_tts_endpoint"),
            api_key=config.get("api_key") or config.get("tts_api_key") or config.get("minimax_api_key"),
            model=config.get("model") or config.get("tts_model"),
            timeout_seconds=float(config.get("timeout_seconds") or 60),
        )
    if provider in {"doubao", "volcengine", "volcano"}:
        return DoubaoTTSAdapter(
            endpoint=config.get("endpoint") or config.get("tts_endpoint") or config.get("doubao_tts_endpoint"),
            api_key=config.get("api_key") or config.get("tts_api_key") or config.get("doubao_api_key"),
            model=config.get("model") or config.get("tts_model"),
            app_id=config.get("app_id") or config.get("doubao_app_id"),
            timeout_seconds=float(config.get("timeout_seconds") or 60),
        )
    raise TTSAdapterError(f"Unsupported TTS provider: {provider}", code="PROVIDER_UNAVAILABLE")


def _tts_provider(config: dict[str, Any]) -> str:
    provider = (
        config.get("tts_provider")
        or config.get("voice_provider")
        or config.get("provider")
        or _tts_env_provider()
        or "step"
    )
    return str(provider).strip().lower()


def _tts_env_provider() -> str | None:
    return _non_empty_str(os.environ.get("TTS_PROVIDER") or os.environ.get("VOICE_TTS_PROVIDER"))


def _step_config_value(config: dict[str, Any], *keys: str, generic_key: str | None = None) -> str | None:
    for key in keys:
        value = _non_empty_str(config.get(key))
        if value:
            return value

    if generic_key and _generic_step_config_allowed(config):
        return _non_empty_str(config.get(generic_key))
    return None


def _generic_step_config_allowed(config: dict[str, Any]) -> bool:
    provider = _non_empty_str(config.get("provider"))
    if provider and provider.strip().lower() in {"step", "stepfun", "step-tts", "step_tts"}:
        return True
    return not any(
        _non_empty_str(config.get(key))
        for key in (
            "deepseek_api_key",
            "deepseek_base_url",
            "translation_provider",
            "asr_provider",
            "minimax_api_key",
            "doubao_api_key",
        )
    )


def _json_tts_request(
    *,
    provider: str,
    endpoint: str,
    api_key: str,
    model: str | None,
    timeout_seconds: float,
    request: TTSRequest,
    extra: dict[str, Any] | None = None,
) -> TTSResult:
    payload: dict[str, Any] = {
        "model": model,
        "target_language": request.target_language,
        "text": request.text,
        "voice_id": request.voice_id,
        "target_duration_ms": request.target_duration_ms,
        "speed": request.speed,
        "style": request.style,
    }
    if extra:
        payload.update(extra)
    body = json.dumps(payload).encode("utf-8")
    http_request = HttpRequest(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(http_request, timeout=timeout_seconds) as response:  # noqa: S310 - endpoint is server config.
            raw = response.read()
    except HTTPError as exc:
        raise TTSAdapterError(_http_error_message(exc), code=_http_error_code(exc.code)) from exc
    except URLError as exc:
        raise TTSAdapterError(str(exc.reason), code="PROVIDER_UNAVAILABLE") from exc

    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise TTSAdapterError(f"{provider} TTS response was not valid JSON") from exc

    audio = _extract_audio(data)
    if not audio:
        raise TTSAdapterError(f"{provider} TTS response did not include audio bytes")
    actual_duration_ms = _int_or_none(
        data.get("actual_duration_ms") or data.get("duration_ms") or _nested(data, "data", "actual_duration_ms")
    )
    if actual_duration_ms is None:
        actual_duration_ms = _estimate_duration_ms(request.text)
    provider_task_id = str(
        data.get("provider_task_id")
        or data.get("task_id")
        or data.get("id")
        or _nested(data, "data", "task_id")
        or f"{provider}_sync"
    )
    return TTSResult(
        audio=audio,
        actual_duration_ms=actual_duration_ms,
        provider=provider,
        provider_task_id=provider_task_id,
        model=model,
    )


def _temporary_audio_path() -> Path:
    handle = tempfile.NamedTemporaryFile(prefix="step_tts_", suffix=".audio", delete=False)
    handle.close()
    return Path(handle.name)


def _step_instruction(configured_instruction: str | None, request: TTSRequest) -> str:
    instruction = configured_instruction or request.style
    if instruction:
        return instruction
    return "自然、清晰地朗读文本。"


def _step_provider_task_id(response: Any, request: TTSRequest) -> str:
    http_response = getattr(response, "response", None)
    headers = getattr(http_response, "headers", None)
    request_id = None
    if headers is not None:
        request_id = headers.get("x-request-id") or headers.get("x-step-request-id")
    if request_id:
        return str(request_id)
    return f"step_tts_{request.segment_id or 'sync'}"


def _step_error(exc: Exception) -> TTSAdapterError:
    openai_errors = _openai_error_types()
    if openai_errors is not None:
        rate_limit_error, timeout_error, connection_error, status_error, api_error = openai_errors
        if isinstance(exc, rate_limit_error):
            return TTSAdapterError(_openai_error_message(exc, "Step TTS rate limit exceeded"), code="PROVIDER_RATE_LIMITED")
        if isinstance(exc, timeout_error):
            return TTSAdapterError("Step TTS request timed out", code="PROVIDER_UNAVAILABLE")
        if isinstance(exc, connection_error):
            return TTSAdapterError(_openai_error_message(exc, "Step TTS provider unavailable"), code="PROVIDER_UNAVAILABLE")
        if isinstance(exc, status_error):
            status_code = int(getattr(getattr(exc, "response", None), "status_code", 0) or 0)
            return TTSAdapterError(_openai_error_message(exc, f"Step TTS HTTP {status_code}"), code=_http_error_code(status_code))
        if isinstance(exc, api_error):
            return TTSAdapterError(_openai_error_message(exc, "Step TTS API request failed"))

    if isinstance(exc, TimeoutError):
        return TTSAdapterError("Step TTS request timed out", code="PROVIDER_UNAVAILABLE")
    if isinstance(exc, OSError):
        return TTSAdapterError(f"Step TTS provider unavailable: {exc}", code="PROVIDER_UNAVAILABLE")
    return TTSAdapterError(f"Step TTS request failed: {exc}")


def _openai_error_types() -> tuple[type[Exception], type[Exception], type[Exception], type[Exception], type[Exception]] | None:
    try:
        from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError, RateLimitError
    except Exception:
        return None
    return RateLimitError, APITimeoutError, APIConnectionError, APIStatusError, APIError


def _openai_error_message(exc: Exception, fallback: str) -> str:
    message = str(exc).strip()
    return message or fallback


def _audio_duration_ms(audio: bytes) -> int | None:
    if not audio:
        return None
    try:
        with wave.open(BytesIO(audio), "rb") as handle:
            framerate = handle.getframerate()
            if framerate <= 0:
                return None
            return int(round(handle.getnframes() * 1000 / framerate))
    except wave.Error:
        return None


def _extract_audio(data: dict[str, Any]) -> bytes | None:
    value = (
        data.get("audio_base64")
        or data.get("audio")
        or _nested(data, "data", "audio_base64")
        or _nested(data, "data", "audio")
    )
    if isinstance(value, str):
        try:
            return base64.b64decode(value)
        except Exception as exc:
            raise TTSAdapterError("TTS response audio_base64 was invalid") from exc
    return None


def _http_error_code(status_code: int) -> str:
    if status_code == 429:
        return "PROVIDER_RATE_LIMITED"
    if status_code in {502, 503, 504}:
        return "PROVIDER_UNAVAILABLE"
    return "TTS_FAILED"


def _http_error_message(exc: HTTPError) -> str:
    detail = exc.read().decode("utf-8", errors="ignore")
    return detail or f"TTS provider HTTP {exc.code}"


def _silent_wav(duration_ms: int, *, sample_rate: int) -> bytes:
    duration_ms = max(0, int(duration_ms))
    sample_count = int(sample_rate * duration_ms / 1000)
    frames = b"\x00\x00" * sample_count
    buffer = BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(frames)
    return buffer.getvalue()


def _estimate_duration_ms(text: str) -> int:
    return max(500, min(8000, len(text.strip()) * 80))


def _nested(value: dict[str, Any], *keys: str) -> Any:
    current: Any = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _non_empty_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
