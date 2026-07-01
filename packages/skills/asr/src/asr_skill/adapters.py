from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


LANGUAGE_TO_WHISPER = {
    "zh-CN": "zh",
    "en-US": "en",
    "es-ES": "es",
    "es-MX": "es",
    "pt-BR": "pt",
}

WHISPER_TO_LANGUAGE = {
    "zh": "zh-CN",
    "cn": "zh-CN",
    "en": "en-US",
    "es": "es-ES",
    "pt": "pt-BR",
}


class ASRAdapterError(RuntimeError):
    def __init__(self, message: str, *, code: str = "ASR_FAILED") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ASRRequest:
    audio_asset_id: str
    source_language: str = "auto"
    enable_diarization: bool = False
    audio_uri: str | None = None
    audio_path: str | None = None


@dataclass(frozen=True)
class TranscriptSegment:
    start_ms: int
    end_ms: int
    text: str
    speaker_id: str | None = None
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "text": self.text,
            "speaker_id": self.speaker_id,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class SpeakerTurn:
    start_ms: int
    end_ms: int
    speaker_id: str
    confidence: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "speaker_id": self.speaker_id,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class ASRResult:
    detected_language: str | None
    segments: list[TranscriptSegment]
    provider: str
    model: str | None = None
    speaker_timeline: list[SpeakerTurn] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def raw_transcript(self) -> dict[str, Any]:
        return {
            "detected_language": self.detected_language,
            "segments": [segment.to_dict() for segment in self.segments],
            "speaker_timeline": [turn.to_dict() for turn in self.speaker_timeline],
        }


@dataclass(frozen=True)
class DiarizationResult:
    speaker_timeline: list[SpeakerTurn]
    provider: str
    model: str | None = None


class ASRAdapterPort(Protocol):
    provider: str
    model: str | None

    def transcribe(self, request: ASRRequest) -> ASRResult:
        ...

    def diarize(
        self,
        request: ASRRequest,
        *,
        transcript: dict[str, Any] | None = None,
    ) -> DiarizationResult:
        ...


class MockASRAdapter:
    provider = "mock"
    model = "mock-asr"

    def __init__(
        self,
        *,
        detected_language: str | None = "zh-CN",
        segments: list[TranscriptSegment | dict[str, Any]] | None = None,
        speaker_timeline: list[SpeakerTurn | dict[str, Any]] | None = None,
        fail: bool = False,
        failure_message: str = "Mock ASR failed",
    ) -> None:
        self.detected_language = detected_language
        self.segments = [_coerce_transcript_segment(item) for item in (segments or [])]
        self.speaker_timeline = [_coerce_speaker_turn(item) for item in (speaker_timeline or [])]
        self.fail = fail
        self.failure_message = failure_message

    def transcribe(self, request: ASRRequest) -> ASRResult:
        if self.fail:
            raise ASRAdapterError(self.failure_message)
        detected_language = self.detected_language
        if detected_language is None and request.source_language != "auto":
            detected_language = request.source_language
        speaker_timeline = self.speaker_timeline if request.enable_diarization else []
        return ASRResult(
            detected_language=detected_language,
            segments=list(self.segments),
            speaker_timeline=list(speaker_timeline),
            provider=self.provider,
            model=self.model,
        )

    def diarize(
        self,
        request: ASRRequest,
        *,
        transcript: dict[str, Any] | None = None,
    ) -> DiarizationResult:
        if self.fail:
            raise ASRAdapterError(self.failure_message)
        if transcript:
            timeline = _speaker_timeline_from_transcript(transcript)
            if timeline:
                return DiarizationResult(timeline, provider=self.provider, model=self.model)
        return DiarizationResult(list(self.speaker_timeline), provider=self.provider, model=self.model)


class FasterWhisperAdapter:
    provider = "faster-whisper"

    def __init__(
        self,
        *,
        model_size: str = "small",
        device: str = "auto",
        compute_type: str = "float32",  # macOS ARM doesn't support efficient float16
        **model_kwargs: Any,
    ) -> None:
        self.model = model_size
        self.device = device
        self.compute_type = compute_type
        self.model_kwargs = model_kwargs
        self._model: Any | None = None

    def transcribe(self, request: ASRRequest) -> ASRResult:
        try:
            from faster_whisper import WhisperModel
        except Exception as exc:  # pragma: no cover - optional provider
            raise ASRAdapterError(
                "faster-whisper is not installed",
                code="PROVIDER_UNAVAILABLE",
            ) from exc

        if self._model is None:
            self._model = WhisperModel(
                self.model,
                device=self.device,
                compute_type=self.compute_type,
                **self.model_kwargs,
            )

        language = LANGUAGE_TO_WHISPER.get(request.source_language)
        audio_input = request.audio_path or request.audio_uri or request.audio_asset_id
        try:
            segments_iter, info = self._model.transcribe(audio_input, language=language)
            segments = [
                TranscriptSegment(
                    start_ms=_seconds_to_ms(item.start),
                    end_ms=_seconds_to_ms(item.end),
                    text=item.text or "",
                    confidence=_avg_logprob_to_confidence(getattr(item, "avg_logprob", None)),
                )
                for item in segments_iter
            ]
        except Exception as exc:  # pragma: no cover - provider boundary
            raise ASRAdapterError("faster-whisper transcription failed") from exc

        detected = WHISPER_TO_LANGUAGE.get(str(getattr(info, "language", "")).lower())
        return ASRResult(
            detected_language=detected or (request.source_language if request.source_language != "auto" else None),
            segments=segments,
            provider=self.provider,
            model=self.model,
            raw={"duration": getattr(info, "duration", None)},
        )

    def diarize(
        self,
        request: ASRRequest,
        *,
        transcript: dict[str, Any] | None = None,
    ) -> DiarizationResult:
        raise ASRAdapterError("faster-whisper does not provide diarization in this adapter")


class WhisperXAdapter:
    provider = "whisperx"

    def __init__(
        self,
        *,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "float32",
        **model_kwargs: Any,
    ) -> None:
        self.model = model_size
        self.device = device
        self.compute_type = compute_type
        self.model_kwargs = model_kwargs
        self._model: Any | None = None

    def transcribe(self, request: ASRRequest) -> ASRResult:
        try:
            import whisperx
        except Exception as exc:  # pragma: no cover - optional provider
            raise ASRAdapterError("whisperx is not installed", code="PROVIDER_UNAVAILABLE") from exc

        audio_input = request.audio_path or request.audio_uri or request.audio_asset_id
        language = LANGUAGE_TO_WHISPER.get(request.source_language)
        try:
            if self._model is None:
                self._model = whisperx.load_model(
                    self.model,
                    self.device,
                    compute_type=self.compute_type,
                    **self.model_kwargs,
                )
            result = self._model.transcribe(audio_input, language=language)
        except Exception as exc:  # pragma: no cover - provider boundary
            raise ASRAdapterError("whisperx transcription failed") from exc

        segments = [
            TranscriptSegment(
                start_ms=_seconds_to_ms(item.get("start", 0)),
                end_ms=_seconds_to_ms(item.get("end", 0)),
                text=str(item.get("text") or ""),
                confidence=_clip_confidence(item.get("score") or item.get("confidence")),
            )
            for item in result.get("segments", [])
        ]
        detected = WHISPER_TO_LANGUAGE.get(str(result.get("language", "")).lower())
        return ASRResult(
            detected_language=detected or (request.source_language if request.source_language != "auto" else None),
            segments=segments,
            provider=self.provider,
            model=self.model,
            raw={"language": result.get("language")},
        )

    def diarize(
        self,
        request: ASRRequest,
        *,
        transcript: dict[str, Any] | None = None,
    ) -> DiarizationResult:
        raise ASRAdapterError("WhisperX diarization requires a configured pyannote pipeline")


def adapter_from_config(config: dict[str, Any] | None = None) -> ASRAdapterPort:
    config = config or {}
    provider = str(config.get("provider") or config.get("asr_provider") or "faster-whisper").lower()
    if provider == "mock":
        return MockASRAdapter(
            detected_language=config.get("detected_language", "zh-CN"),
            segments=config.get("mock_segments") or config.get("segments") or [],
            speaker_timeline=config.get("mock_speaker_timeline") or config.get("speaker_timeline") or [],
            fail=bool(config.get("fail")),
            failure_message=str(config.get("failure_message") or "Mock ASR failed"),
        )
    if provider in {"faster-whisper", "faster_whisper"}:
        return FasterWhisperAdapter(
            model_size=str(config.get("model") or config.get("model_size") or "small"),
            device=str(config.get("device") or "auto"),
            compute_type=str(config.get("compute_type") or "default"),
        )
    if provider == "whisperx":
        return WhisperXAdapter(
            model_size=str(config.get("model") or config.get("model_size") or "small"),
            device=str(config.get("device") or "cpu"),
            compute_type=str(config.get("compute_type") or "float32"),
        )
    raise ASRAdapterError(f"Unsupported ASR provider: {provider}", code="PROVIDER_UNAVAILABLE")


def _coerce_transcript_segment(value: TranscriptSegment | dict[str, Any]) -> TranscriptSegment:
    if isinstance(value, TranscriptSegment):
        return value
    start_ms = _time_to_ms(value.get("start_ms", value.get("start", 0)))
    end_ms = _time_to_ms(value.get("end_ms", value.get("end", 0)))
    return TranscriptSegment(
        start_ms=start_ms,
        end_ms=end_ms,
        text=str(value.get("text") or ""),
        speaker_id=_optional_str(value.get("speaker_id") or value.get("speaker")),
        confidence=_clip_confidence(value.get("confidence") or value.get("score")),
    )


def _coerce_speaker_turn(value: SpeakerTurn | dict[str, Any]) -> SpeakerTurn:
    if isinstance(value, SpeakerTurn):
        return value
    speaker = value.get("speaker_id") or value.get("speaker") or value.get("label")
    return SpeakerTurn(
        start_ms=_time_to_ms(value.get("start_ms", value.get("start", 0))),
        end_ms=_time_to_ms(value.get("end_ms", value.get("end", 0))),
        speaker_id=str(speaker or "speaker_unknown"),
        confidence=_clip_confidence(value.get("confidence") or value.get("score")),
    )


def _speaker_timeline_from_transcript(transcript: dict[str, Any]) -> list[SpeakerTurn]:
    raw_timeline = transcript.get("speaker_timeline") or transcript.get("diarization") or []
    if raw_timeline:
        return [_coerce_speaker_turn(item) for item in raw_timeline]
    turns: list[SpeakerTurn] = []
    for segment in transcript.get("segments") or transcript.get("raw_segments") or []:
        speaker = segment.get("speaker_id") or segment.get("speaker")
        if not speaker:
            continue
        turns.append(
            SpeakerTurn(
                start_ms=_time_to_ms(segment.get("start_ms", segment.get("start", 0))),
                end_ms=_time_to_ms(segment.get("end_ms", segment.get("end", 0))),
                speaker_id=str(speaker),
                confidence=_clip_confidence(segment.get("confidence") or segment.get("score")),
            )
        )
    return turns


def _time_to_ms(value: Any) -> int:
    if isinstance(value, str):
        value = float(value)
    if isinstance(value, float) and value < 1000:
        return _seconds_to_ms(value)
    return int(round(float(value)))


def _seconds_to_ms(value: float | int) -> int:
    return int(round(float(value) * 1000))


def _clip_confidence(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, numeric))


def _avg_logprob_to_confidence(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric >= 0:
        return _clip_confidence(numeric)
    return _clip_confidence(1.0 + numeric)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None
