from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import pytest

from media_skills import (
    FFmpegAdapter,
    MockSourceSeparationAdapter,
    StoragePathResolver,
    extract_audio,
    parse_ffprobe_json,
    private_uri,
    probe,
    separate_sources,
    separation_path,
    source_path,
    storage_key_for_asset,
)
from media_skills.ffmpeg import CommandResult
from media_skills.paths import AssetType


def _request(skill_name: str, payload: dict, *, config: dict | None = None) -> dict:
    return {
        "skill_name": skill_name,
        "skill_version": "1.0.0",
        "project_id": "proj_123",
        "run_id": "run_123",
        "input": payload,
        "config": config or {},
        "idempotency_key": f"run_123:{skill_name}:v1",
    }


def _ffprobe_payload(
    *,
    duration: str = "128.456",
    format_name: str = "mov,mp4,m4a,3gp,3g2,mj2",
    major_brand: str = "isom",
    streams: list[dict] | None = None,
) -> str:
    return json.dumps(
        {
            "streams": streams
            if streams is not None
            else [
                {
                    "index": 0,
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": "30000/1001",
                    "duration": duration,
                },
                {
                    "index": 1,
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "sample_rate": "48000",
                    "channels": 2,
                    "channel_layout": "stereo",
                    "bit_rate": "128000",
                    "duration": duration,
                    "tags": {"language": "und"},
                },
            ],
            "format": {
                "format_name": format_name,
                "duration": duration,
                "size": "1048576",
                "tags": {"major_brand": major_brand},
            },
        }
    )


class FakeRunner:
    def __init__(
        self,
        *,
        probe_stdout: str | None = None,
        probe_returncode: int = 0,
        probe_stderr: str = "",
        ffmpeg_returncode: int = 0,
        ffmpeg_stderr: str = "",
    ) -> None:
        self.probe_stdout = probe_stdout or _ffprobe_payload()
        self.probe_returncode = probe_returncode
        self.probe_stderr = probe_stderr
        self.ffmpeg_returncode = ffmpeg_returncode
        self.ffmpeg_stderr = ffmpeg_stderr
        self.calls: list[list[str]] = []

    def run(self, args: Sequence[str], *, timeout_seconds: int | None = None) -> CommandResult:
        call = list(args)
        self.calls.append(call)
        if Path(call[0]).name == "ffprobe":
            return CommandResult(call, self.probe_returncode, self.probe_stdout, self.probe_stderr)
        if Path(call[0]).name == "ffmpeg":
            if self.ffmpeg_returncode == 0:
                Path(call[-1]).parent.mkdir(parents=True, exist_ok=True)
                Path(call[-1]).write_bytes(b"mock wav")
            return CommandResult(call, self.ffmpeg_returncode, "", self.ffmpeg_stderr)
        raise AssertionError(f"unexpected command: {call}")


def test_parse_ffprobe_output_extracts_media_metadata() -> None:
    metadata = parse_ffprobe_json(_ffprobe_payload())

    assert metadata.duration_ms == 128456
    assert metadata.format == "mp4"
    assert metadata.codec == "h264"
    assert metadata.has_audio is True
    assert metadata.video_codec == "h264"
    assert metadata.audio_codec == "aac"
    assert metadata.width == 1920
    assert metadata.height == 1080
    assert metadata.fps == 29.97
    assert metadata.size_bytes == 1048576
    assert metadata.audio_stream is not None
    assert metadata.audio_stream.to_dict() == {
        "codec": "aac",
        "sample_rate": 48000,
        "channels": 2,
        "channel_layout": "stereo",
        "bit_rate": 128000,
        "duration_ms": 128456,
        "language": "und",
    }


@pytest.mark.parametrize(
    ("probe_stdout", "error_code"),
    [
        (
            _ffprobe_payload(
                streams=[
                    {
                        "index": 0,
                        "codec_type": "video",
                        "codec_name": "h264",
                        "width": 1280,
                        "height": 720,
                        "avg_frame_rate": "25/1",
                        "duration": "90.0",
                    }
                ]
            ),
            "NO_AUDIO_TRACK",
        ),
        (_ffprobe_payload(format_name="matroska,webm", major_brand="", duration="90.0"), "INVALID_VIDEO"),
        (_ffprobe_payload(duration="181.0"), "VIDEO_TOO_LONG"),
    ],
)
def test_probe_maps_media_boundary_errors(probe_stdout: str, error_code: str, tmp_path: Path) -> None:
    runner = FakeRunner(probe_stdout=probe_stdout)
    response = probe(
        _request(
            "media.probe",
            {"source_video": {"asset_id": "asset_video", "uri": "/tmp/source.mp4", "type": "source_video"}},
            config={"storage_root": str(tmp_path)},
        ),
        ffmpeg=FFmpegAdapter(runner=runner),
    )

    assert response["status"] == "failed"
    assert response["error"]["code"] == error_code
    assert response["usage"] == {}
    assert response["assets"] == []


def test_probe_maps_ffprobe_command_failure_to_invalid_video(tmp_path: Path) -> None:
    runner = FakeRunner(probe_returncode=1, probe_stderr="Invalid data found when processing input")

    response = probe(
        _request(
            "media.probe",
            {"source_video": {"asset_id": "asset_video", "uri": "/tmp/source.mp4", "type": "source_video"}},
            config={"storage_root": str(tmp_path)},
        ),
        ffmpeg=FFmpegAdapter(runner=runner),
    )

    assert response["status"] == "failed"
    assert response["error"] == {
        "code": "INVALID_VIDEO",
        "message": "Invalid data found when processing input",
    }


def test_path_generation_follows_spec_section_8(tmp_path: Path) -> None:
    assert source_path("proj_123", "mp4") == "projects/proj_123/source/source.mp4"
    assert source_path("proj_123", "wav") == "projects/proj_123/source/source.wav"
    assert separation_path("proj_123", "vocals") == "projects/proj_123/separation/vocals.wav"
    assert separation_path("proj_123", "background") == "projects/proj_123/separation/background.wav"
    assert storage_key_for_asset("proj_123", AssetType.SOURCE_AUDIO) == "projects/proj_123/source/source.wav"

    resolver = StoragePathResolver(tmp_path)
    output = resolver.output_location("proj_123", AssetType.BACKGROUND_AUDIO)

    assert output.storage_key == "projects/proj_123/separation/background.wav"
    assert output.uri == "storage://private/projects/proj_123/separation/background.wav"
    assert output.local_path == tmp_path / "projects/proj_123/separation/background.wav"


def test_extract_audio_invokes_ffmpeg_and_returns_source_audio_asset(tmp_path: Path) -> None:
    source_key = source_path("proj_123", "mp4")
    source_file = tmp_path / source_key
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"mock video")
    runner = FakeRunner()

    response = extract_audio(
        _request(
            "media.extract_audio",
            {
                "source_video": {
                    "asset_id": "asset_video",
                    "project_id": "proj_123",
                    "type": "source_video",
                    "language": None,
                    "uri": private_uri(source_key),
                    "format": "mp4",
                    "duration_ms": 128456,
                    "size_bytes": 100,
                }
            },
            config={"storage_root": str(tmp_path)},
        ),
        ffmpeg=FFmpegAdapter(runner=runner),
    )

    assert response["status"] == "succeeded"
    assert response["error"] is None
    assert response["outputs"]["duration_ms"] == 128456
    assert response["outputs"]["audio_asset_id"] == response["assets"][0]["asset_id"]
    assert response["assets"][0]["type"] == "source_audio"
    assert response["assets"][0]["uri"] == "storage://private/projects/proj_123/source/source.wav"
    assert response["assets"][0]["format"] == "wav"
    assert response["assets"][0]["size_bytes"] == len(b"mock wav")
    assert response["usage"] == {"provider": "ffmpeg"}

    assert len(runner.calls) == 2
    assert runner.calls[0][0] == "ffprobe"
    assert runner.calls[1][0] == "ffmpeg"
    assert runner.calls[1][runner.calls[1].index("-map") + 1] == "0:a:0"
    assert runner.calls[1][-1] == str(tmp_path / "projects/proj_123/source/source.wav")


def test_separate_sources_success_response_with_mock_adapter(tmp_path: Path) -> None:
    source_key = source_path("proj_123", "wav")
    source_file = tmp_path / source_key
    source_file.parent.mkdir(parents=True)
    source_file.write_bytes(b"mock source wav")

    response = separate_sources(
        _request(
            "audio.separate_sources",
            {
                "mode": "vocal_background",
                "source_audio": {
                    "asset_id": "asset_audio",
                    "project_id": "proj_123",
                    "type": "source_audio",
                    "language": None,
                    "uri": private_uri(source_key),
                    "format": "wav",
                    "duration_ms": 128456,
                    "size_bytes": 200,
                },
            },
            config={"storage_root": str(tmp_path)},
        ),
        separation_adapter=MockSourceSeparationAdapter(quality_score=0.82),
    )

    assert response["status"] == "succeeded"
    assert response["error"] is None
    assert response["outputs"]["quality_score"] == 0.82
    assert response["outputs"]["source_vocal_asset_id"] == response["assets"][0]["asset_id"]
    assert response["outputs"]["background_asset_id"] == response["assets"][1]["asset_id"]
    assert [asset["type"] for asset in response["assets"]] == ["source_vocal", "background_audio"]
    assert response["assets"][0]["uri"] == "storage://private/projects/proj_123/separation/vocals.wav"
    assert response["assets"][1]["uri"] == "storage://private/projects/proj_123/separation/background.wav"
    assert response["assets"][0]["duration_ms"] == 128456
    assert response["usage"] == {"provider": "mock-demucs", "model": "mock-vocal-background"}
    assert (tmp_path / "projects/proj_123/separation/vocals.wav").is_file()
    assert (tmp_path / "projects/proj_123/separation/background.wav").is_file()


def test_separate_sources_failure_response_with_mock_adapter(tmp_path: Path) -> None:
    response = separate_sources(
        _request(
            "audio.separate_sources",
            {
                "mode": "vocal_background",
                "source_audio": {
                    "asset_id": "asset_audio",
                    "project_id": "proj_123",
                    "type": "source_audio",
                    "language": None,
                    "uri": "/tmp/source.wav",
                    "format": "wav",
                    "duration_ms": 1000,
                    "size_bytes": 200,
                },
            },
            config={"storage_root": str(tmp_path)},
        ),
        separation_adapter=MockSourceSeparationAdapter(should_fail=True),
    )

    assert response == {
        "status": "failed",
        "outputs": {},
        "assets": [],
        "quality_flags": [],
        "usage": {},
        "error": {
            "code": "SOURCE_SEPARATION_FAILED",
            "message": "Mock source separation failed",
        },
    }
