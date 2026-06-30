from __future__ import annotations

from pathlib import Path
from typing import Sequence
from zipfile import ZipFile

from packaging_skills import (
    FFmpegAudioAdapter,
    format_srt_timestamp,
    format_vtt_timestamp,
    generate_subtitles,
    make_manifest,
    mix_audio,
    package_zip,
    private_uri,
    stitch_vocals,
)
from packaging_skills.ffmpeg import CommandResult
from packaging_skills.paths import audio_path, package_path, separation_path, source_path, subtitle_path, tts_segment_path


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


def _segments() -> list[dict]:
    return [
        {
            "segment_id": "seg_0001",
            "project_id": "proj_123",
            "index": 1,
            "start_ms": 1200,
            "end_ms": 3600,
            "source_text": "你到底想怎么样？",
        },
        {
            "segment_id": "seg_0002",
            "project_id": "proj_123",
            "index": 2,
            "start_ms": 4000,
            "end_ms": 6100,
            "source_text": "马上离开。",
        },
    ]


class FakeRunner:
    def __init__(self, *, returncode: int = 0, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        self.calls: list[list[str]] = []

    def run(self, args: Sequence[str], *, timeout_seconds: int | None = None) -> CommandResult:
        call = list(args)
        self.calls.append(call)
        if self.returncode == 0:
            output = Path(call[-1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"mock audio")
        return CommandResult(call, self.returncode, "", self.stderr)


def _asset(asset_type: str, storage_key: str, *, language: str | None = None, fmt: str = "wav", duration_ms: int | None = 6100) -> dict:
    return {
        "asset_id": f"asset_{asset_type}_{language or 'source'}",
        "project_id": "proj_123",
        "type": asset_type,
        "language": language,
        "uri": private_uri(storage_key),
        "storage_key": storage_key,
        "format": fmt,
        "duration_ms": duration_ms,
        "size_bytes": 10,
    }


def test_timestamp_formatting_uses_srt_and_vtt_millisecond_separators() -> None:
    assert format_srt_timestamp(3_723_456) == "01:02:03,456"
    assert format_vtt_timestamp(3_723_456) == "01:02:03.456"
    assert format_srt_timestamp(-1) == "00:00:00,000"


def test_subtitle_generate_uses_active_translation_and_segment_timeline(tmp_path: Path) -> None:
    response = generate_subtitles(
        _request(
            "subtitle.generate",
            {
                "target_language": "en-US",
                "segments": _segments(),
                "translations": [
                    {
                        "translation_id": "tr_old",
                        "segment_id": "seg_0001",
                        "target_language": "en-US",
                        "text": "Old inactive line",
                        "status": "completed",
                        "active": False,
                    },
                    {
                        "translation_id": "tr_active",
                        "segment_id": "seg_0001",
                        "target_language": "en-US",
                        "text": "What exactly do you want from me?",
                        "status": "completed",
                        "active": True,
                    },
                    {
                        "translation_id": "tr_second",
                        "segment_id": "seg_0002",
                        "target_language": "en-US",
                        "text": "Leave right now.",
                        "status": "completed",
                    },
                ],
            },
            config={"storage_root": str(tmp_path)},
        )
    )

    assert response["status"] == "succeeded"
    assert [asset["type"] for asset in response["assets"]] == ["subtitle_srt", "subtitle_vtt"]
    srt_path = tmp_path / subtitle_path("proj_123", "en-US", "srt")
    vtt_path = tmp_path / subtitle_path("proj_123", "en-US", "vtt")
    assert srt_path.read_text(encoding="utf-8").splitlines()[1] == "00:00:01,200 --> 00:00:03,600"
    assert "What exactly do you want" in srt_path.read_text(encoding="utf-8")
    assert "Old inactive line" not in srt_path.read_text(encoding="utf-8")
    assert vtt_path.read_text(encoding="utf-8").startswith("WEBVTT\n\n00:00:01.200 --> 00:00:03.600")
    assert "{" not in vtt_path.read_text(encoding="utf-8")


def test_stitch_vocals_places_tts_by_segment_start_and_flags_long_audio(tmp_path: Path) -> None:
    for segment_id in ("seg_0001", "seg_0002"):
        key = tts_segment_path("proj_123", "en-US", segment_id)
        local = tmp_path / key
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(b"tts")
    runner = FakeRunner()

    response = stitch_vocals(
        _request(
            "audio.stitch_vocals",
            {
                "target_language": "en-US",
                "segments": _segments(),
                "tts_segment_audio": [
                    {
                        "segment_id": "seg_0001",
                        "uri": private_uri(tts_segment_path("proj_123", "en-US", "seg_0001")),
                        "duration_ms": 1000,
                    },
                    {
                        "segment_id": "seg_0002",
                        "uri": private_uri(tts_segment_path("proj_123", "en-US", "seg_0002")),
                        "duration_ms": 2500,
                    },
                ],
            },
            config={"storage_root": str(tmp_path)},
        ),
        ffmpeg=FFmpegAudioAdapter(runner=runner),
    )

    assert response["status"] == "succeeded"
    assert response["assets"][0]["type"] == "target_vocal"
    assert response["assets"][0]["uri"] == private_uri(audio_path("proj_123", "en-US", "vocal"))
    assert response["assets"][0]["duration_ms"] == 6500
    assert {flag["code"] for flag in response["quality_flags"]} == {"TTS_LONGER_THAN_SEGMENT"}
    call = runner.calls[0]
    filter_graph = call[call.index("-filter_complex") + 1]
    assert "adelay=1200|1200" in filter_graph
    assert "adelay=4000|4000" in filter_graph
    assert "apad=pad_dur=1.400,atrim=duration=2.400" in filter_graph
    assert (tmp_path / audio_path("proj_123", "en-US", "vocal")).read_bytes() == b"mock audio"


def test_mix_audio_registers_target_mix_asset_and_uses_background_as_base(tmp_path: Path) -> None:
    background_key = separation_path("proj_123", "background")
    vocal_key = audio_path("proj_123", "en-US", "vocal")
    for key in (background_key, vocal_key):
        local = tmp_path / key
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(b"audio")
    runner = FakeRunner()

    response = mix_audio(
        _request(
            "audio.mix",
            {
                "target_language": "en-US",
                "background_audio": _asset("background_audio", background_key, fmt="wav"),
                "target_vocal": _asset("target_vocal", vocal_key, language="en-US", fmt="wav"),
            },
            config={"storage_root": str(tmp_path)},
        ),
        ffmpeg=FFmpegAudioAdapter(runner=runner),
    )

    assert response["status"] == "succeeded"
    assert response["assets"][0]["type"] == "target_mix_audio"
    assert response["assets"][0]["format"] == "m4a"
    assert response["outputs"]["target_mix_audio_asset_id"] == response["assets"][0]["asset_id"]
    call = runner.calls[0]
    assert call[call.index("-i") + 1] == str(tmp_path / background_key)
    assert "[bg][vocal]amix=inputs=2:duration=first" in call[call.index("-filter_complex") + 1]
    assert (tmp_path / audio_path("proj_123", "en-US", "mix")).is_file()


def test_package_manifest_structure_uses_playable_urls_not_private_storage_uris() -> None:
    response = make_manifest(
        _request(
            "package.manifest",
            {
                "version_id": "ver_001",
                "assets": [
                    _asset("source_video", source_path("proj_123", "mp4"), fmt="mp4"),
                    _asset("source_audio", source_path("proj_123", "wav"), fmt="wav"),
                    _asset("subtitle_srt", subtitle_path("proj_123", "en-US", "srt"), language="en-US", fmt="srt"),
                    _asset("subtitle_vtt", subtitle_path("proj_123", "en-US", "vtt"), language="en-US", fmt="vtt"),
                    _asset("target_mix_audio", audio_path("proj_123", "en-US", "mix"), language="en-US", fmt="m4a"),
                ],
            },
            config={"cdn_base_url": "https://cdn.example.com"},
        )
    )

    manifest = response["outputs"]["manifest"]
    assert response["status"] == "succeeded"
    assert manifest["project_id"] == "proj_123"
    assert manifest["version_id"] == "ver_001"
    assert manifest["video"]["url"] == "https://cdn.example.com/projects/proj_123/source/source.mp4"
    assert manifest["subtitles"] == [
        {
            "language": "en-US",
            "label": "English",
            "format": "vtt",
            "url": "https://cdn.example.com/projects/proj_123/subtitles/en-US.vtt",
        }
    ]
    assert manifest["audio_tracks"][0]["language"] == "source"
    assert manifest["audio_tracks"][1]["language"] == "en-US"
    assert manifest["downloads"][0]["type"] == "package_zip"
    urls = [manifest["video"]["url"], *(item["url"] for item in manifest["subtitles"]), *(item["url"] for item in manifest["audio_tracks"]), *(item["url"] for item in manifest["downloads"])]
    assert all(not url.startswith("storage://") for url in urls)


def test_package_zip_contains_manifest_and_expected_result_assets(tmp_path: Path) -> None:
    keys = [
        source_path("proj_123", "mp4"),
        source_path("proj_123", "wav"),
        separation_path("proj_123", "background"),
        separation_path("proj_123", "vocals"),
        subtitle_path("proj_123", "en-US", "srt"),
        subtitle_path("proj_123", "en-US", "vtt"),
        tts_segment_path("proj_123", "en-US", "seg_0001"),
        audio_path("proj_123", "en-US", "mix"),
    ]
    for key in keys:
        local = tmp_path / key
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(f"file:{key}".encode("utf-8"))

    assets = [
        _asset("source_video", source_path("proj_123", "mp4"), fmt="mp4"),
        _asset("source_audio", source_path("proj_123", "wav"), fmt="wav"),
        _asset("background_audio", separation_path("proj_123", "background"), fmt="wav"),
        _asset("source_vocal", separation_path("proj_123", "vocals"), fmt="wav"),
        _asset("subtitle_srt", subtitle_path("proj_123", "en-US", "srt"), language="en-US", fmt="srt"),
        _asset("subtitle_vtt", subtitle_path("proj_123", "en-US", "vtt"), language="en-US", fmt="vtt"),
        _asset("tts_segment_audio", tts_segment_path("proj_123", "en-US", "seg_0001"), language="en-US", fmt="wav"),
        _asset("target_mix_audio", audio_path("proj_123", "en-US", "mix"), language="en-US", fmt="m4a"),
    ]

    response = package_zip(
        _request(
            "package.zip",
            {
                "version_id": "ver_001",
                "manifest": {
                    "project_id": "proj_123",
                    "version_id": "ver_001",
                    "video": {"url": "/video", "duration_ms": 6100},
                    "subtitles": [],
                    "audio_tracks": [],
                    "downloads": [],
                },
                "assets": assets,
                "include_intermediate_assets": True,
            },
            config={"storage_root": str(tmp_path)},
        )
    )

    assert response["status"] == "succeeded"
    zip_path = tmp_path / package_path("proj_123", "ver_001")
    with ZipFile(zip_path) as archive:
        assert sorted(archive.namelist()) == sorted(
            [
                "manifest.json",
                "source/source.mp4",
                "source/source.wav",
                "separation/background.wav",
                "separation/vocals.wav",
                "subtitles/en-US.srt",
                "subtitles/en-US.vtt",
                "tts/en-US/seg_0001.wav",
                "audio/en-US.mix.m4a",
            ]
        )
    assert sorted(response["outputs"]["zip_entries"]) == sorted(ZipFile(zip_path).namelist())
