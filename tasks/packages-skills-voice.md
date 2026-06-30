# 模块任务卡 · packages/skills/voice

> 阶段③ 分配给模块 Agent 的工作单元。一卡一模块。
> 关联：`docs/spec.md`（FROZEN）、`docs/prd.md`、`docs/architecture.md`

## 归属

- 模块：packages/skills/voice
- 负责 Agent：module-developer
- 代码目录：`packages/skills/voice`
- 复杂度：complex

## 任务范围

- 实现 `voice.synthesize` Skill，覆盖 Agent+Skill 架构 §4 与 Spec §11.3 TTS Adapter。
- 使用 MiniMax 或豆包/火山引擎作为默认 TTS Provider Adapter，provider 可配置，不写死业务逻辑（架构 §6.5、PRD §5.3）。
- 为每个 active Translation + Segment 生成一个 TTS 分段音频，符合 Spec §10.1。
- target_duration_ms 来源于 Segment 时长；实际时长偏差 MVP 建议 <= 20%，超出时打 quality_flags，不强制失败（Spec §4.6）。
- 支持按 speaker_id 选择 target_language 对应 voice_id（Spec §4.5、PRD §5.3）。
- 支持单句、指定 segment_ids、整语言的 TTS 重跑（Spec §7.8、Agent+Skill 架构 §5.3）。
- 输出 TTSJob 实体符合 Spec §4.6，并产出 `tts_segment_audio` MediaAsset。
- 文件路径遵守 Spec §8：`projects/{project_id}/tts/{language}/{segment_id}.wav`。
- 边界：只生成分段 TTS 音频；不拼接人声、不混音、不生成字幕或 zip；不启用未授权声音克隆。

## 输入

- 依赖的接口：
  - Spec §6 Skill 调用契约。
  - `packages/shared-types` 的 Segment、Translation、Speaker、TTSJob、TTS Adapter、错误码类型。
  - TTS Adapter（Spec §11.3）：MiniMax/豆包默认实现，mock 实现用于测试。
  - 对象存储端口：写入 TTS 音频资产。
  - Voice 配置端口：读取默认 voice_id、speaker target_voice_map、provider 配置。
- 依赖的数据表：
  - 逻辑读取 `segments` / `segment_versions`。
  - 逻辑读取 active `translations` / `translation_versions`。
  - 逻辑读取 `speakers`。
  - 逻辑写入 `tts_jobs`。
  - 逻辑写入 `media_assets`：tts_segment_audio。
  - 逻辑关联 `skill_runs`：记录 provider、provider_task_id、error。

## 产出

- `voice.synthesize` Skill 实现。
- TTS Provider Adapter 抽象与默认实现。
- 语速、目标时长、voice_id 选择策略。
- TTSJob 状态管理输出。
- 单元测试和集成测试：
  - Segment 时长到 target_duration_ms。
  - speaker_id 到 voice_id 映射。
  - 单句/整语言重跑。
  - 20% 时长偏差 quality_flags。
  - provider 失败、限流、不可用错误映射。

## 验收标准

- [ ] 输入输出符合 Spec §6 和 Spec §11.3。
- [ ] 每个被选中的 Segment 生成一个 TTSJob 和一个 `tts_segment_audio` MediaAsset（Spec §4.2、§4.6、§10.1）。
- [ ] TTSJob 记录 target_language、text、voice_id、target_duration_ms、speed、status、actual_duration_ms、provider、provider_task_id、error（Spec §4.6）。
- [ ] actual_duration_ms 偏差超过 20% 时返回 quality_flags，不直接失败（Spec §4.6）。
- [ ] 单句失败可重试，重试由 Runtime 创建新的 SkillRun，Skill 返回结构化失败（Spec §4.9、§6）。
- [ ] 不启用声音克隆默认能力，未授权 voice clone 请求必须拒绝或忽略（Spec §4.5、§13）。
- [ ] 文件路径符合 Spec §8。

## 备注

- MVP 不承诺唇形级同步和原演员声音复刻；质量问题通过 flags 暴露给校对页。
- Provider Adapter 必须支持 mock，避免测试依赖真实外部 TTS 服务。
