# 模块任务卡 · packages/agent-runtime

> 阶段③ 分配给模块 Agent 的工作单元。一卡一模块。
> 关联：`docs/spec.md`（FROZEN）、`docs/architecture.md`、`docs/agent-skill-architecture.md`

## 归属

- 模块：packages/agent-runtime
- 负责 Agent：module-developer
- 代码目录：`packages/agent-runtime`
- 复杂度：complex

## 任务范围

- 实现轻量 Agent Runtime，遵守 Agent+Skill 架构 §10：固定模板 + 少量条件分支，不做自主规划。
- 实现 Spec §4.8 AgentRun、§4.9 SkillRun、§4.10 SkillDefinition 的读写语义。
- 实现 Spec §5 Agent Run Status、Task Status、Task Type 状态流转。
- 实现 Spec §6 Skill 调用契约：结构化 request/response、idempotency_key、usage、assets、quality_flags、error。
- 实现 Agent+Skill 架构 §5 的模板：
  - `subtitle_draft`：`media.probe` -> `media.extract_audio` -> `audio.separate_sources` -> `asr.transcribe` -> `transcript.normalize_segments` -> `localization.translate` -> `subtitle.generate` -> `pause_for_proofreading`。
  - `full_dubbing`：`media.probe` -> `media.extract_audio` -> `audio.separate_sources` -> `asr.transcribe` -> `asr.diarize` -> `transcript.normalize_segments` -> `localization.translate` -> `pause_for_proofreading` -> `subtitle.generate` -> `voice.synthesize` -> `audio.stitch_vocals` -> `audio.mix` -> `package.manifest` -> `package.zip`。
  - `rerun_segments`：`voice.synthesize selected_segments` -> `audio.stitch_vocals target_language` -> `audio.mix target_language` -> `package.manifest`。
  - `package_only`：`package.manifest` 和/或 `package.zip`。
- 维护 Run Context（Agent+Skill 架构 §6）：project、version、template、source_language、target_languages、assets、segments_version、translation_versions、human_checkpoints。
- 实现人工协同边界（Agent+Skill 架构 §8）：ASR/翻译初稿后暂停、首次完整 TTS 前暂停，不覆盖 locked segment。
- 实现重试、跳过、局部重跑和失败记录；重试必须生成新的 SkillRun，不覆盖历史记录（Spec §4.9、§6）。
- 边界：Runtime 只编排 Skill，不直接执行 FFmpeg、模型推理、TTS、混音；不持有前端可见密钥；不绕过 proofreading。

## 输入

- 依赖的接口：
  - `packages/shared-types` 的 Skill Contract、实体、状态、错误码、模板枚举。
  - Skill Registry：查询 SkillDefinition、默认版本、默认 provider、timeout、retry_limit。
  - Task Queue：投递和消费 Skill 调用任务。
  - Skill Runner Port：按 Spec §6 调用 `packages/skills/*`。
  - Repository：读写 AgentRun、SkillRun、Task、Project 状态、资产引用、版本引用。
- 依赖的数据表：
  - `agent_runs`
  - `skill_runs`
  - `skill_definitions`
  - `tasks`
  - `projects`
  - `media_assets`
  - `segments` / `segment_versions`
  - `translations` / `translation_versions`
  - `tts_jobs`
  - `versions`

## 产出

- Runtime 包代码：模板执行器、Run Context 管理、Skill Registry Client、队列适配、Skill 调用器、重试策略、checkpoint 处理。
- 对 `apps/api` 暴露的接口：
  - `createRun(projectId, template, config)`
  - `continueRun(runId, checkpoint)`
  - `rerunLanguage(projectId, targetLanguage, steps)`
  - `rerunSegments(projectId, targetLanguage, segmentIds, steps)`
  - `getRunStatus(runId)`
- 单元测试和集成测试：
  - 模板步骤顺序。
  - human checkpoint 暂停和继续。
  - Skill failed/retry/new SkillRun 记录。
  - locked segment 防覆盖。
  - 多目标语言循环与局部重跑。

## 验收标准

- [ ] `subtitle_draft` 和 `full_dubbing` 步骤顺序与 Agent+Skill 架构 §5 完全一致。
- [ ] 每次 Skill 调用生成 SkillRun，记录 skill_name、skill_version、status、input_refs、output_refs、provider、model、error（Spec §4.9）。
- [ ] Skill request/response 严格使用 Spec §6 契约，失败时保留上游资产并记录 error.code/error.message。
- [ ] Run Context 包含 Agent+Skill 架构 §6 最小字段，并能在步骤之间传递资产和版本引用。
- [ ] proofreading checkpoint 将 AgentRun 置为 `waiting_human`，只有 API 调用 continue 后才能进入 TTS/混音/打包（Spec §5.3、§7.4）。
- [ ] 重试不会覆盖旧 SkillRun，幂等键避免重复产物污染（Spec §4.9、§6）。
- [ ] Runtime 不直接导入具体 FFmpeg/ASR/TTS/LLM provider SDK。

## 备注

- MVP 不需要多 Agent 对话或自然语言规划。
- 模板步骤允许配置开关，例如是否启用 diarization、是否生成预览 MP4，但不得改变 Spec 定义的核心状态语义。
