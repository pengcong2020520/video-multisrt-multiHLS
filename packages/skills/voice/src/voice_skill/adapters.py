from __future__ import annotations

import base64
import json
import wave
from dataclasses import dataclass
from io import BytesIO
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


def adapter_from_config(config: dict[str, Any] | None = None) -> TTSAdapterPort:
    config = config or {}
    provider = str(config.get("provider") or config.get("tts_provider") or "minimax").lower()
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
