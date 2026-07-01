"""Composite skill runner that routes requests to the correct skill package.

The agent runtime invokes skills by name (e.g. ``media.probe``,
``asr.transcribe``).  This runner inspects the ``skill_name`` on the incoming
``SkillRequest`` and dispatches to the matching skill package:

* media.probe / media.extract_audio / audio.separate_sources → ``media_skills.invoke()``
* asr.transcribe / asr.diarize / transcript.normalize_segments → ``ASRSkillRunner``
* localization.translate                                     → ``LocalizationSkillRunner``
* voice.synthesize                                           → ``VoiceSkillRunner``
* subtitle.generate / audio.stitch_vocals / audio.mix /
  package.manifest / package.zip                             → ``packaging_skills.invoke()``

Each skill package uses a different call convention:

* ``media_skills`` and ``packaging_skills`` expose a module-level ``invoke()``
  function that accepts the request (dict or dataclass) and returns a dict.
* ``asr_skill``, ``localization_skill``, and ``voice_skill`` expose a ``Runner``
  class with an ``invoke(request)`` method.

All skills return a ``dict[str, Any]`` mapping that the runtime normalises via
``SkillResponse.from_mapping``.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from agent_runtime.contracts import SkillRequest, SkillResponse, SkillRunnerPort


# ---------------------------------------------------------------------------
# sys.path bootstrap for skill packages.
#
# The skill packages live as siblings under packages/skills/<name>/src and are
# not installed into the API venv.  We add their ``src`` directories to
# ``sys.path`` once so that ``import media_skills``, ``import asr_skill``, etc.
# work from within apps/api.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SKILLS_ROOT = _REPO_ROOT / "packages" / "skills"

_SKILL_SRC_PATHS = [
    _SKILLS_ROOT / "media" / "src",
    _SKILLS_ROOT / "asr" / "src",
    _SKILLS_ROOT / "localization" / "src",
    _SKILLS_ROOT / "voice" / "src",
    _SKILLS_ROOT / "packaging" / "src",
]
for _path in _SKILL_SRC_PATHS:
    _text = str(_path)
    if _path.exists() and _text not in sys.path:
        sys.path.append(_text)


# Lazy imports so that a missing optional dependency in one skill package does
# not break the import of the runner (and therefore the whole API app).
def _import_media_skills() -> Any:
    import media_skills.skills as module  # type: ignore[import-not-found]

    return module


def _import_packaging_skills() -> Any:
    import packaging_skills.skills as module  # type: ignore[import-not-found]

    return module


def _import_asr_runner() -> Any:
    from asr_skill.skills import ASRSkillRunner  # type: ignore[import-not-found]

    return ASRSkillRunner


def _import_localization_runner() -> Any:
    from localization_skill.skills import (  # type: ignore[import-not-found]
        LocalizationSkillRunner,
    )

    return LocalizationSkillRunner


def _import_voice_runner() -> Any:
    from voice_skill.skills import VoiceSkillRunner  # type: ignore[import-not-found]

    return VoiceSkillRunner


# Skill-name → package mapping.  Updated lazily on first use so import errors
# surface only when the relevant skill is actually invoked.
_MEDIA_SKILLS = {
    "media.probe",
    "media.extract_audio",
    "audio.separate_sources",
}
_ASR_SKILLS = {
    "asr.transcribe",
    "asr.diarize",
    "transcript.normalize_segments",
}
_LOCALIZATION_SKILLS = {
    "localization.translate",
}
_VOICE_SKILLS = {
    "voice.synthesize",
}
_PACKAGING_SKILLS = {
    "subtitle.generate",
    "audio.stitch_vocals",
    "audio.mix",
    "package.manifest",
    "package.zip",
}


class CompositeSkillRunner(SkillRunnerPort):
    """Route ``SkillRequest`` to the appropriate skill package."""

    def __init__(
        self,
        *,
        media_adapter_overrides: dict[str, Any] | None = None,
        asr_runner: Any | None = None,
        localization_runner: Any | None = None,
        voice_runner: Any | None = None,
        packaging_adapter_overrides: dict[str, Any] | None = None,
    ) -> None:
        self._media_adapter_overrides = media_adapter_overrides or {}
        self._packaging_adapter_overrides = packaging_adapter_overrides or {}
        self._asr_runner = asr_runner
        self._localization_runner = localization_runner
        self._voice_runner = voice_runner
        # Inject storage_root from env so skills can find files on disk
        import os as _os
        _sr = _os.environ.get("STORAGE_ROOT", "./storage")
        # Resolve to absolute path so skills can find files regardless of cwd
        self._storage_root = str(_os.path.abspath(_sr))
        print(f"[CompositeSkillRunner] storage_root={self._storage_root}", flush=True)

    def invoke(self, request: SkillRequest) -> dict[str, Any]:
        skill_name = request.skill_name

        # Inject storage_root + API keys + provider config into request config
        import os as _os
        config = dict(request.config) if request.config else {}
        config.setdefault("storage_root", self._storage_root)
        config.setdefault("local_storage_root", self._storage_root)
        # DeepSeek (translation)
        config.setdefault("provider", "deepseek")
        config.setdefault("api_key", _os.environ.get("DEEPSEEK_API_KEY", ""))
        config.setdefault("deepseek_api_key", _os.environ.get("DEEPSEEK_API_KEY", ""))
        config.setdefault("base_url", _os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"))
        config.setdefault("deepseek_base_url", _os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"))
        config.setdefault("model", _os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"))
        # Step TTS
        config.setdefault("tts_provider", "step")
        config.setdefault("step_api_key", _os.environ.get("STEP_API_KEY", ""))
        config.setdefault("step_base_url", _os.environ.get("STEP_BASE_URL", "https://api.stepfun.com/step_plan/v1"))
        config.setdefault("step_tts_model", _os.environ.get("STEP_TTS_MODEL", "stepaudio-2.5-tts"))
        # ASR
        config.setdefault("asr_provider", "faster-whisper")
        config.setdefault("compute_type", "float32")
        # Create a modified request with the enriched config
        from agent_runtime.contracts import SkillRequest as _SR
        request = _SR(
            skill_name=request.skill_name,
            skill_version=request.skill_version,
            project_id=request.project_id,
            run_id=request.run_id,
            input=request.input,
            config=config,
            idempotency_key=request.idempotency_key,
        )

        try:
            if skill_name in _MEDIA_SKILLS:
                return self._invoke_media(request)
            if skill_name in _ASR_SKILLS:
                return self._invoke_asr(request)
            if skill_name in _LOCALIZATION_SKILLS:
                return self._invoke_localization(request)
            if skill_name in _VOICE_SKILLS:
                return self._invoke_voice(request)
            if skill_name in _PACKAGING_SKILLS:
                return self._invoke_packaging(request)
        except Exception as exc:  # pragma: no cover - defensive boundary
            return SkillResponse.failed("SKILL_RUN_FAILED", str(exc)).__dict__

        return SkillResponse.failed(
            "SKILL_RUN_FAILED",
            f"No skill package registered for skill: {skill_name}",
        ).__dict__

    # ------------------------------------------------------------------
    # Per-package dispatch
    # ------------------------------------------------------------------

    def _invoke_media(self, request: SkillRequest) -> dict[str, Any]:
        module = _import_media_skills()
        return module.invoke(request, **self._media_adapter_overrides)

    def _invoke_asr(self, request: SkillRequest) -> dict[str, Any]:
        runner = self._asr_runner
        if runner is None:
            runner_cls = _import_asr_runner()
            runner = runner_cls()
            self._asr_runner = runner
        return runner.invoke(request)

    def _invoke_localization(self, request: SkillRequest) -> dict[str, Any]:
        runner = self._localization_runner
        if runner is None:
            runner_cls = _import_localization_runner()
            runner = runner_cls()
            self._localization_runner = runner
        return runner.invoke(request)

    def _invoke_voice(self, request: SkillRequest) -> dict[str, Any]:
        runner = self._voice_runner
        if runner is None:
            runner_cls = _import_voice_runner()
            runner = runner_cls()
            self._voice_runner = runner
        return runner.invoke(request)

    def _invoke_packaging(self, request: SkillRequest) -> dict[str, Any]:
        module = _import_packaging_skills()
        return module.invoke(request, **self._packaging_adapter_overrides)


__all__ = ["CompositeSkillRunner"]
