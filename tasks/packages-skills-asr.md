# 模块任务卡 · packages/skills/asr

> 阶段③ 分配给模块 Agent 的工作单元。一卡一模块。
> 关联：`docs/spec.md`（FROZEN）、`docs/architecture.md`、`docs/agent-skill-architecture.md`

## 归属

- 模块：packages/skills/asr
- 负责 Agent：module-developer
- 代码目录：`packages/skills/asr`
- 复杂度：complex

## 任务范围

- 实现转写与句段规整 Skill，覆盖 Agent+Skill 架构 §4：
  - `asr.transcribe`
  - `asr.diarize`
  - `transcript.normalize_segments`
- 使用 faster-whisper 或 WhisperX 作为默认 ASR Adapter，符合架构文档 §6.3 与 Spec §11.1。
- 可选使用 WhisperX/pyannote 说话人识别能力；MVP 不要求真实人物身份识别（Spec §4.5）。
- 将模型原始输出转换为统一 Segment（Spec §4.3），不能将模型原始结构直接暴露给业务。
- 句段规整规则：
  - `start_ms < end_ms`。
  - 不跨越过长静音。
  - 默认单句建议 0.8-8 秒。
  - 生成 index、speaker_id、source_language、source_text、asr_confidence、quality_flags。
- 输出 ASR JSON 路径遵守 Spec §8：`projects/{project_id}/asr/source_segments.json`。
- 边界：只做 ASR、diarization 和 Segment normalization；不做翻译、字幕生成、TTS 或混音；不覆盖 locked Segment。

## 输入

- 依赖的接口：
  - Spec §6 Skill 调用契约。
  - `packages/shared-types` 的 Segment、Speaker、MediaAsset、ASR Adapter、错误码类型。
  - 对象存储端口：读取 `source_vocal`，写入 ASR 原始 JSON 或规整结果。
  - ASR Adapter（Spec §11.1）：faster-whisper/WhisperX 默认实现，mock 实现用于测试。
  - 可选 Diarization Adapter。
- 依赖的数据表：
  - 逻辑读取 `media_assets`：source_vocal。
  - 逻辑写入 `segments` / `segment_versions`。
  - 逻辑写入或更新 `speakers`。
  - 逻辑关联 `skill_runs`：由 Runtime/Worker 记录。

## 产出

- Skill 实现：
  - `asr.transcribe`：输入 source_vocal、source_language、enable_diarization，输出 detected_language、raw transcript、ASR asset。
  - `asr.diarize`：输入 source_vocal 或 transcript，输出 speaker timeline。
  - `transcript.normalize_segments`：输入 raw transcript 与 speaker timeline，输出 Spec §4.3 Segment 列表。
- ASR Adapter 封装和错误映射。
- Segment normalization 算法与质量提示。
- 单元测试和集成测试：
  - raw transcript 到 Segment 的时间轴规整。
  - 过短/过长/空文本/重叠时间段处理。
  - diarization speaker_id 映射。
  - locked segment 防覆盖。
  - `ASR_FAILED` 错误响应。

## 验收标准

- [ ] `asr.transcribe` 输出符合 Spec §11.1，失败时返回 `ASR_FAILED` 或 provider 错误码（Spec §12）。
- [ ] `transcript.normalize_segments` 输出的每个 Segment 符合 Spec §4.3 规则，`start_ms < end_ms`。
- [ ] Segment 不直接暴露 Whisper/faster-whisper/WhisperX 原始字段名作为业务契约。
- [ ] `asr.diarize` 可在启用时生成稳定 speaker_id；未启用时仍能生成可用 Segment。
- [ ] 自动步骤不会覆盖 `locked=true` 的既有 Segment（Spec §4.3、§6）。
- [ ] ASR JSON 或规整结果资产路径符合 Spec §8。
- [ ] 测试覆盖中文/英文/auto 源语言配置（Spec §3）。

## 备注

- 多人重叠对白准确率不是 MVP 承诺，遇到重叠和低置信度应打 quality_flags。
- 如果本地模型不可用，必须通过 Adapter 返回结构化失败，不让 Runtime 感知 provider 内部异常。
