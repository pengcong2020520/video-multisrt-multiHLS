from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from .errors import ErrorCode, PackagingSkillError


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class VocalClip:
    segment_id: str
    input_path: str
    start_ms: int
    segment_duration_ms: int
    actual_duration_ms: int | None

    @property
    def pad_ms(self) -> int:
        if self.actual_duration_ms is None:
            return 0
        return max(0, self.segment_duration_ms - self.actual_duration_ms)

    @property
    def is_longer_than_segment(self) -> bool:
        return self.actual_duration_ms is not None and self.actual_duration_ms > self.segment_duration_ms


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
            raise PackagingSkillError(ErrorCode.MIXING_FAILED, f"Media tool not found: {args[0]}") from exc
        except subprocess.TimeoutExpired as exc:
            raise PackagingSkillError(ErrorCode.MIXING_FAILED, f"Media command timed out: {args[0]}") from exc
        return CommandResult(
            args=list(args),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


class FFmpegAudioAdapter:
    def __init__(
        self,
        *,
        runner: CommandRunner | None = None,
        ffmpeg_bin: str = "ffmpeg",
        timeout_seconds: int = 300,
    ) -> None:
        self.runner = runner or SubprocessCommandRunner()
        self.ffmpeg_bin = ffmpeg_bin
        self.timeout_seconds = timeout_seconds

    def stitch_vocals(
        self,
        clips: Sequence[VocalClip],
        output_path: str | Path,
        *,
        sample_rate: int = 48000,
        channels: int = 2,
    ) -> None:
        if not clips:
            raise PackagingSkillError(ErrorCode.MIXING_FAILED, "At least one TTS segment audio input is required")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        input_args: list[str] = []
        filter_parts: list[str] = []
        for index, clip in enumerate(clips):
            input_args.extend(["-i", clip.input_path])
            filter_parts.append(_clip_filter(index, clip, sample_rate=sample_rate, channels=channels))
        labels = "".join(f"[a{index}]" for index in range(len(clips)))
        filter_graph = (
            ";".join(filter_parts)
            + ";"
            + f"{labels}amix=inputs={len(clips)}:duration=longest:normalize=0[out]"
        )
        result = self.runner.run(
            [
                self.ffmpeg_bin,
                "-y",
                *input_args,
                "-filter_complex",
                filter_graph,
                "-map",
                "[out]",
                "-ar",
                str(sample_rate),
                "-ac",
                str(channels),
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ],
            timeout_seconds=self.timeout_seconds,
        )
        if result.returncode != 0:
            raise PackagingSkillError(ErrorCode.MIXING_FAILED, _clean_stderr(result.stderr) or "ffmpeg vocal stitch failed")

    def mix(
        self,
        background_path: str | Path,
        target_vocal_path: str | Path,
        output_path: str | Path,
        *,
        sample_rate: int = 48000,
        channels: int = 2,
        background_volume: float = 1.0,
        vocal_volume: float = 1.0,
        bitrate: str = "192k",
    ) -> None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        layout = _channel_layout(channels)
        filter_graph = (
            f"[0:a]aresample={sample_rate},aformat=channel_layouts={layout},volume={background_volume:g}[bg];"
            f"[1:a]aresample={sample_rate},aformat=channel_layouts={layout},volume={vocal_volume:g}[vocal];"
            "[bg][vocal]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[out]"
        )
        result = self.runner.run(
            [
                self.ffmpeg_bin,
                "-y",
                "-i",
                str(background_path),
                "-i",
                str(target_vocal_path),
                "-filter_complex",
                filter_graph,
                "-map",
                "[out]",
                "-ar",
                str(sample_rate),
                "-ac",
                str(channels),
                "-c:a",
                "aac",
                "-b:a",
                bitrate,
                "-movflags",
                "+faststart",
                str(output_path),
            ],
            timeout_seconds=self.timeout_seconds,
        )
        if result.returncode != 0:
            raise PackagingSkillError(ErrorCode.MIXING_FAILED, _clean_stderr(result.stderr) or "ffmpeg audio mix failed")


def _clip_filter(index: int, clip: VocalClip, *, sample_rate: int, channels: int) -> str:
    layout = _channel_layout(channels)
    chain = f"[{index}:a]aresample={sample_rate},aformat=channel_layouts={layout}"
    if clip.pad_ms > 0:
        duration = _seconds(clip.segment_duration_ms)
        pad = _seconds(clip.pad_ms)
        chain += f",apad=pad_dur={pad},atrim=duration={duration}"
    delay = max(0, int(clip.start_ms))
    chain += f",adelay={delay}|{delay}[a{index}]"
    return chain


def _channel_layout(channels: int) -> str:
    return "mono" if channels == 1 else "stereo"


def _seconds(ms: int) -> str:
    return f"{max(0, ms) / 1000:.3f}"


def _clean_stderr(value: str) -> str:
    return " ".join(value.strip().split())
