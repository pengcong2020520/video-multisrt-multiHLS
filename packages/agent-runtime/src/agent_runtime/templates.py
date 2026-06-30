from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.domain.enums import AgentTemplate, TaskType


LanguageScope = Literal["once", "target"]


@dataclass(frozen=True)
class RuntimeStep:
    name: str
    task_type: TaskType | None = None
    language_scope: LanguageScope = "once"
    checkpoint: str | None = None

    @property
    def is_checkpoint(self) -> bool:
        return self.checkpoint is not None


def skill(name: str, task_type: TaskType, language_scope: LanguageScope = "once") -> RuntimeStep:
    return RuntimeStep(name=name, task_type=task_type, language_scope=language_scope)


def checkpoint(name: str, checkpoint_name: str) -> RuntimeStep:
    return RuntimeStep(name=name, checkpoint=checkpoint_name)


TEMPLATE_STEPS: dict[AgentTemplate, list[RuntimeStep]] = {
    AgentTemplate.SUBTITLE_DRAFT: [
        skill("media.probe", TaskType.PROBE_MEDIA),
        skill("media.extract_audio", TaskType.EXTRACT_AUDIO),
        skill("audio.separate_sources", TaskType.SEPARATE_SOURCES),
        skill("asr.transcribe", TaskType.ASR),
        skill("transcript.normalize_segments", TaskType.SEGMENT_NORMALIZE),
        skill("localization.translate", TaskType.TRANSLATE, "target"),
        skill("subtitle.generate", TaskType.GENERATE_SUBTITLE, "target"),
        checkpoint("pause_for_proofreading", "proofreading"),
    ],
    AgentTemplate.FULL_DUBBING: [
        skill("media.probe", TaskType.PROBE_MEDIA),
        skill("media.extract_audio", TaskType.EXTRACT_AUDIO),
        skill("audio.separate_sources", TaskType.SEPARATE_SOURCES),
        skill("asr.transcribe", TaskType.ASR),
        skill("asr.diarize", TaskType.ASR),
        skill("transcript.normalize_segments", TaskType.SEGMENT_NORMALIZE),
        skill("localization.translate", TaskType.TRANSLATE, "target"),
        checkpoint("pause_for_proofreading", "proofreading"),
        skill("subtitle.generate", TaskType.GENERATE_SUBTITLE, "target"),
        skill("voice.synthesize", TaskType.TTS, "target"),
        skill("audio.stitch_vocals", TaskType.STITCH_TARGET_VOCAL, "target"),
        skill("audio.mix", TaskType.MIX_AUDIO, "target"),
        skill("package.manifest", TaskType.PACKAGE_OUTPUTS),
        skill("package.zip", TaskType.PACKAGE_OUTPUTS),
    ],
    AgentTemplate.RERUN_SEGMENTS: [
        skill("voice.synthesize", TaskType.TTS, "target"),
        skill("audio.stitch_vocals", TaskType.STITCH_TARGET_VOCAL, "target"),
        skill("audio.mix", TaskType.MIX_AUDIO, "target"),
        skill("package.manifest", TaskType.PACKAGE_OUTPUTS),
    ],
    AgentTemplate.PACKAGE_ONLY: [
        skill("package.manifest", TaskType.PACKAGE_OUTPUTS),
        skill("package.zip", TaskType.PACKAGE_OUTPUTS),
    ],
}


def task_plan_for_template(template: AgentTemplate | str, context: dict[str, Any] | None = None) -> list[TaskType]:
    return [
        step.task_type
        for step in runtime_plan_for_template(template, context)
        if step.task_type is not None
    ]


def runtime_plan_for_template(
    template: AgentTemplate | str,
    context: dict[str, Any] | None = None,
) -> list[RuntimeStep]:
    template = AgentTemplate(template)
    context = context or {}
    steps = list(TEMPLATE_STEPS[template])

    if template in {AgentTemplate.SUBTITLE_DRAFT, AgentTemplate.FULL_DUBBING}:
        if context.get("enable_source_separation") is False:
            steps = [step for step in steps if step.name != "audio.separate_sources"]
        if template == AgentTemplate.FULL_DUBBING and context.get("enable_diarization") is False:
            steps = [step for step in steps if step.name != "asr.diarize"]

    if template == AgentTemplate.PACKAGE_ONLY:
        include_manifest = context.get("include_manifest", True)
        include_zip = context.get("include_zip", not context.get("manifest_only", False))
        selected = []
        if include_manifest:
            selected.append("package.manifest")
        if include_zip:
            selected.append("package.zip")
        if not selected:
            selected = ["package.manifest"]
        steps = [step for step in steps if step.name in selected]

    if template == AgentTemplate.RERUN_SEGMENTS and context.get("steps"):
        requested = set(context["steps"])
        selected_names: set[str] = {"package.manifest"}
        if "tts" in requested:
            selected_names.add("voice.synthesize")
        if "mix" in requested:
            selected_names.update({"audio.stitch_vocals", "audio.mix"})
        if "subtitle" in requested:
            selected_names.add("subtitle.generate")
        base_steps = list(TEMPLATE_STEPS[template])
        if "subtitle.generate" in selected_names:
            base_steps.insert(0, skill("subtitle.generate", TaskType.GENERATE_SUBTITLE, "target"))
        steps = [step for step in base_steps if step.name in selected_names]

    return steps


def template_step_names(template: AgentTemplate | str, context: dict[str, Any] | None = None) -> list[str]:
    return [step.name for step in runtime_plan_for_template(template, context)]


def task_requires_language(task_type: TaskType) -> bool:
    return task_type in {
        TaskType.TRANSLATE,
        TaskType.GENERATE_SUBTITLE,
        TaskType.TTS,
        TaskType.STITCH_TARGET_VOCAL,
        TaskType.MIX_AUDIO,
    }
