from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from .errors import SourceSeparationError
from .ffmpeg import CommandRunner, SubprocessCommandRunner
from .types import SeparationResult


class SourceSeparationAdapter(Protocol):
    provider: str
    model: str | None

    def separate(
        self,
        source_audio_path: str | Path,
        vocals_path: str | Path,
        background_path: str | Path,
        *,
        work_dir: str | Path,
    ) -> SeparationResult:
        ...


@dataclass(frozen=True)
class DemucsConfig:
    command: Sequence[str] = ("python", "-m", "demucs")
    model: str = "htdemucs"
    quality_score: float | None = 0.78
    timeout_seconds: int = 900


class DemucsSourceSeparationAdapter:
    provider = "demucs"

    def __init__(
        self,
        *,
        runner: CommandRunner | None = None,
        config: DemucsConfig | None = None,
    ) -> None:
        self.runner = runner or SubprocessCommandRunner()
        self.config = config or DemucsConfig()
        self.model = self.config.model

    def separate(
        self,
        source_audio_path: str | Path,
        vocals_path: str | Path,
        background_path: str | Path,
        *,
        work_dir: str | Path,
    ) -> SeparationResult:
        source = Path(source_audio_path)
        output_root = Path(work_dir)
        args = [
            *list(self.config.command),
            "--two-stems",
            "vocals",
            "-n",
            self.config.model,
            "-o",
            str(output_root),
            str(source),
        ]
        result = self.runner.run(args, timeout_seconds=self.config.timeout_seconds)
        if result.returncode != 0:
            message = " ".join(result.stderr.strip().split()) or "Demucs command failed"
            raise SourceSeparationError(message)

        generated_dir = output_root / self.config.model / source.stem
        generated_vocals = generated_dir / "vocals.wav"
        generated_background = generated_dir / "no_vocals.wav"
        if not generated_vocals.is_file() or not generated_background.is_file():
            raise SourceSeparationError("Demucs output files were not created")

        Path(vocals_path).parent.mkdir(parents=True, exist_ok=True)
        Path(background_path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(generated_vocals, vocals_path)
        shutil.copyfile(generated_background, background_path)
        return SeparationResult(
            quality_score=self.config.quality_score,
            quality_flags=[
                {
                    "code": "source_separation_quality_estimated",
                    "message": "Demucs does not provide a calibrated quality score; this score is adapter supplied.",
                    "severity": "info",
                }
            ],
        )


class MockSourceSeparationAdapter:
    provider = "mock-demucs"
    model = "mock-vocal-background"

    def __init__(self, *, should_fail: bool = False, quality_score: float | None = 0.78) -> None:
        self.should_fail = should_fail
        self.quality_score = quality_score

    def separate(
        self,
        source_audio_path: str | Path,
        vocals_path: str | Path,
        background_path: str | Path,
        *,
        work_dir: str | Path,
    ) -> SeparationResult:
        if self.should_fail:
            raise SourceSeparationError("Mock source separation failed")
        Path(work_dir).mkdir(parents=True, exist_ok=True)
        Path(vocals_path).parent.mkdir(parents=True, exist_ok=True)
        Path(background_path).parent.mkdir(parents=True, exist_ok=True)
        Path(vocals_path).write_bytes(b"mock vocals\n")
        Path(background_path).write_bytes(b"mock background\n")
        return SeparationResult(quality_score=self.quality_score, quality_flags=[])
