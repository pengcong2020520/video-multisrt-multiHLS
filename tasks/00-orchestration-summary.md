# 阶段③ 编排汇总

> 依据 `docs/spec.md`（FROZEN）、`docs/architecture.md`、`docs/agent-skill-architecture.md`、`docs/prd.md` 和 `.claude/agents/orchestrator.md` 拆分。
> MVP 使用固定编排模板：字幕初稿模板与完整外切模板；不做 Agent 自主规划。

## 模块清单

| 任务卡 | 代码目录 | 复杂度 | 主要职责 |
| --- | --- | --- | --- |
| [apps-web.md](./apps-web.md) | `apps/web` | complex | 内部运营 Web：上传配置、进度、校对、预览、下载、Skill 配置查看。 |
| [apps-api.md](./apps-api.md) | `apps/api` | complex | Spec §7 最小 API、项目/资产/句段/版本/审计管理、调用 Agent Runtime。 |
| [packages-agent-runtime.md](./packages-agent-runtime.md) | `packages/agent-runtime` | complex | 固定模板编排、Run Context、SkillRun 记录、人工暂停、重试和局部重跑。 |
| [packages-skills-media.md](./packages-skills-media.md) | `packages/skills/media` | complex | `media.probe`、`media.extract_audio`、`audio.separate_sources`。 |
| [packages-skills-asr.md](./packages-skills-asr.md) | `packages/skills/asr` | complex | `asr.transcribe`、`asr.diarize`、`transcript.normalize_segments`。 |
| [packages-skills-localization.md](./packages-skills-localization.md) | `packages/skills/localization` | complex | `localization.translate` 与 DeepSeek/LLM 适配。 |
| [packages-skills-voice.md](./packages-skills-voice.md) | `packages/skills/voice` | complex | `voice.synthesize`、TTS Provider 适配、TTSJob 与时长质量提示。 |
| [packages-skills-packaging.md](./packages-skills-packaging.md) | `packages/skills/packaging` | complex | `subtitle.generate`、`audio.stitch_vocals`、`audio.mix`、`package.manifest`、`package.zip`。 |
| [packages-shared-types.md](./packages-shared-types.md) | `packages/shared-types` | simple | Spec 实体、状态、错误码、Skill Contract、API DTO、文件路径规范。 |

## 依赖关系

- `packages/shared-types` 是所有模块的编译期契约来源，不依赖业务模块。
- `apps/web` 只调用 `apps/api` 暴露的 Spec §7 HTTP API，不直接访问数据库、对象存储、Skill 或模型密钥。
- `apps/api` 只通过 `packages/agent-runtime` 的公开接口创建/继续 Run；不直接执行 FFmpeg、ASR、翻译、TTS、混音。
- `packages/agent-runtime` 只通过 Spec §6 Skill 调用契约调用 Skill；不直接执行模型推理或音视频命令。
- `packages/skills/*` 只实现自身 Skill；模块间不互相导入业务实现，只共享 `packages/shared-types` 契约。
- `packages/skills/packaging` 依赖上游产物引用：segments、translations、tts_segment_audio、background_audio；通过 Skill 输入和资产引用获取，不越界查询其他 Skill 内部状态。

## 建议开发顺序

1. `packages/shared-types`：先固化实体、状态、错误码、API DTO、Skill 输入输出 Schema，作为全仓契约基线。
2. `apps/api` 基础骨架：建立数据库表/Repository、对象存储端口、Spec §7 API 路由空实现和鉴权/审计框架。
3. `packages/agent-runtime`：实现固定模板、Run Context、Skill Registry、SkillRun 记录、人工校对暂停与继续。
4. `packages/skills/media` 与 `packages/skills/asr`：打通上传后到统一 Segment 的前半链路。
5. `packages/skills/localization`：基于 Segment 生成 active Translation，进入 proofreading。
6. `apps/web` 的上传、进度、校对页：前半链路可见可编辑后，再推进配音与打包 UI。
7. `packages/skills/voice`：实现 TTS 分段、音色映射、时长偏差标记和局部重跑基础。
8. `packages/skills/packaging`：生成字幕、混音音轨、manifest 和 zip。
9. `apps/web` 的预览和下载页收口：按 manifest 实现字幕/音轨切换，并跑 Spec §14 三个验收用例。

## 集成验收主线

- Case 1（Spec §14）：中文 2 分钟短剧到 `en-US`，生成 VTT/SRT、英文混合音轨，Web 可切换字幕和音轨。
- Case 2（Spec §14）：英文 1 分钟短剧到 `es-ES`，生成人声替换音轨，保留 BGM，下载结果包。
- Case 3（Spec §14）：修改某个 segment 的英文译文，局部重跑 TTS，重新混音，预览页听到新结果。

## 编排约束

- Spec 是冻结契约；任务执行中发现契约冲突时停止开发并回到规格修订，不在模块内私自扩语义。
- 模块间边界以 Spec §6 Skill 调用契约和 Spec §7 API 为准。
- `locked=true` 的 Segment 不允许被自动重写（Spec §4.3、§6）。
- 每次 Skill 调用必须生成新的 SkillRun，重试不得覆盖历史记录（Spec §4.9、§6）。
- 模型 API key、对象存储私有路径和供应商私有 endpoint 不返回前端（Spec §13）。
