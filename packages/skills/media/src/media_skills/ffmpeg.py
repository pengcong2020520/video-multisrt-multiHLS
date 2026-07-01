from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from .errors import ErrorCode, InvalidVideoError, MediaSkillError
from .types import AudioStreamMetadata, ProbeMetadata


SUPPORTED_VIDEO_FORMATS = {"mp4", "mov"}


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(self, args: Sequence[str], *, timeout_seconds: int | None = None) -> CommandResult:
        ...


class SubprocessCommandRunner:
    def run(self, args: Sequence[str], *, timeout_seconds: int | None = None) -> CommandResult:
        try:
            completed = subprocess.run(
                list(args),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise MediaSkillError(ErrorCode.PROVIDER_UNAVAILABLE, f"Media tool not found: {args[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise MediaSkillError(ErrorCode.SKILL_RUN_FAILED, f"Media command timed out: {args[0]}") from exc
        return CommandResult(
            args=list(args),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


class FFmpegAdapter:
    def __init__(
        self,
        *,
        runner: CommandRunner | None = None,
        ffprobe_bin: str = "ffprobe",
        ffmpeg_bin: str = "ffmpeg",
        timeout_seconds: int = 120,
    ) -> None:
        self.runner = runner or SubprocessCommandRunner()
        self.ffprobe_bin = ffprobe_bin
        self.ffmpeg_bin = ffmpeg_bin
        self.timeout_seconds = timeout_seconds

    def probe(self, input_path: str | Path) -> ProbeMetadata:
        result = self.runner.run(
            [
                self.ffprobe_bin,
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(input_path),
            ],
            timeout_seconds=self.timeout_seconds,
        )
        if result.returncode != 0:
            raise InvalidVideoError(_clean_stderr(result.stderr) or "ffprobe could not read the video")
        return parse_ffprobe_json(result.stdout)

    def extract_audio(self, input_path: str | Path, output_path: str | Path) -> None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        result = self.runner.run(
            [
                self.ffmpeg_bin,
                "-y",
                "-i",
                str(input_path),
                "-map",
                "0:a:0",
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "48000",
                "-ac",
                "2",
                str(output_path),
            ],
            timeout_seconds=self.timeout_seconds,
        )
        if result.returncode != 0:
            raise InvalidVideoError(_clean_stderr(result.stderr) or "ffmpeg could not extract audio")

    def generate_preview(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        max_width: int = 854,
        max_height: int = 480,
        video_bitrate: str = "1000k",
        audio_bitrate: str = "128k",
    ) -> None:
        """Generate a compressed preview video optimized for web playback.

        Uses H.264 + AAC with faststart for streaming.
        Scales down to max_width x max_height while preserving aspect ratio.
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        result = self.runner.run(
            [
                self.ffmpeg_bin,
                "-y",
                "-i",
                str(input_path),
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "28",
                "-maxrate",
                video_bitrate,
                "-bufsize",
                "2000k",
                "-vf",
                f"scale='min({max_width},iw)':'min({max_height},ih)':force_original_aspect_ratio=decrease",
                "-c:a",
                "aac",
                "-b:a",
                audio_bitrate,
                "-movflags",
                "+faststart",
                "-map",
                "0",
                str(output_path),
            ],
            timeout_seconds=self.timeout_seconds,
        )
        if result.returncode != 0:
            raise InvalidVideoError(_clean_stderr(result.stderr) or "ffmpeg could not generate preview")


def parse_ffprobe_json(payload: str) -> ProbeMetadata:
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise InvalidVideoError("ffprobe returned invalid JSON") from exc

    streams = data.get("streams")
    if not isinstance(streams, list):
        raise InvalidVideoError("ffprobe output does not include streams")

    format_info = data.get("format") if isinstance(data.get("format"), dict) else {}
    video_stream = _first_stream(streams, "video")
    audio_stream = _first_stream(streams, "audio")

    duration_ms = _duration_ms(format_info.get("duration"))
    if duration_ms is None:
        stream_durations = [
            value
            for value in (_duration_ms(stream.get("duration")) for stream in streams if isinstance(stream, dict))
            if value is not None
        ]
        duration_ms = max(stream_durations) if stream_durations else None
    if duration_ms is None:
        raise InvalidVideoError("ffprobe output does not include media duration")

    media_format = _normalize_format(format_info)
    video_codec = _str_or_none(video_stream.get("codec_name")) if video_stream else None
    audio_codec = _str_or_none(audio_stream.get("codec_name")) if audio_stream else None

    return ProbeMetadata(
        duration_ms=duration_ms,
        format=media_format,
        codec=video_codec,
        has_audio=audio_stream is not None,
        audio_stream=_audio_stream_metadata(audio_stream) if audio_stream else None,
        video_codec=video_codec,
        audio_codec=audio_codec,
        width=_int_or_none(video_stream.get("width")) if video_stream else None,
        height=_int_or_none(video_stream.get("height")) if video_stream else None,
        fps=_frame_rate(video_stream.get("avg_frame_rate")) if video_stream else None,
        size_bytes=_int_or_none(format_info.get("size")),
        quality_flags=[],
    )


def validate_probe_metadata(metadata: ProbeMetadata, *, max_duration_ms: int) -> None:
    if metadata.format not in SUPPORTED_VIDEO_FORMATS:
        raise MediaSkillError(ErrorCode.INVALID_VIDEO, f"Unsupported video format: {metadata.format}")
    if not metadata.has_audio:
        raise MediaSkillError(ErrorCode.NO_AUDIO_TRACK, "Video does not contain a usable audio track")
    if metadata.duration_ms > max_duration_ms:
        raise MediaSkillError(
            ErrorCode.VIDEO_TOO_LONG,
            f"Video duration {metadata.duration_ms}ms exceeds limit {max_duration_ms}ms",
        )


def _first_stream(streams: list[object], codec_type: str) -> dict[str, object] | None:
    for stream in streams:
        if isinstance(stream, dict) and stream.get("codec_type") == codec_type:
            return stream
    return None


def _normalize_format(format_info: dict[str, object]) -> str:
    names = {
        name.strip().lower()
        for name in str(format_info.get("format_name") or "").split(",")
        if name.strip()
    }
    tags = format_info.get("tags") if isinstance(format_info.get("tags"), dict) else {}
    major_brand = str(tags.get("major_brand") or "").strip().lower()
    if major_brand == "qt" or major_brand == "qt  " or "quicktime" in names:
        return "mov"
    if "mp4" in names or major_brand in {"mp4", "isom", "iso2", "avc1", "m4v"}:
        return "mp4"
    if "mov" in names:
        return "mov"
    return next(iter(names), "unknown")


def _audio_stream_metadata(stream: dict[str, object]) -> AudioStreamMetadata:
    tags = stream.get("tags") if isinstance(stream.get("tags"), dict) else {}
    return AudioStreamMetadata(
        codec=_str_or_none(stream.get("codec_name")),
        sample_rate=_int_or_none(stream.get("sample_rate")),
        channels=_int_or_none(stream.get("channels")),
        channel_layout=_str_or_none(stream.get("channel_layout")),
        bit_rate=_int_or_none(stream.get("bit_rate")),
        duration_ms=_duration_ms(stream.get("duration")),
        language=_str_or_none(tags.get("language")),
    )


def _duration_ms(value: object) -> int | None:
    numeric = _float_or_none(value)
    if numeric is None:
        return None
    return max(0, round(numeric * 1000))


def _frame_rate(value: object) -> float | None:
    if value is None:
        return None
    text = str(value)
    if "/" in text:
        numerator, denominator = text.split("/", 1)
        num = _float_or_none(numerator)
        den = _float_or_none(denominator)
        if not num or not den:
            return None
        return round(num / den, 3)
    return _float_or_none(text)


def _int_or_none(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _clean_stderr(stderr: str) -> str:
    return " ".join(stderr.strip().split())
