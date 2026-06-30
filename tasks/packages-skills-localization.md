# 模块任务卡 · packages/skills/localization

> 阶段③ 分配给模块 Agent 的工作单元。一卡一模块。
> 关联：`docs/spec.md`（FROZEN）、`docs/prd.md`、`docs/architecture.md`

## 归属

- 模块：packages/skills/localization
- 负责 Agent：module-developer
- 代码目录：`packages/skills/localization`
- 复杂度：complex

## 任务范围

- 实现 `localization.translate` Skill，覆盖 Agent+Skill 架构 §4 与 Spec §11.2 Translation Adapter。
- 使用 DeepSeek 作为默认 LLM 适配器，但 provider/model/prompt_version 必须配置化，不写死业务逻辑（架构 §6.4、PRD §4.3）。
- 输入 Segment、source_language、target_language、style、glossary、character_notes、forbidden_terms、length_policy，输出 active Translation。
- 翻译风格遵守 PRD §4.1：短剧本地化、口语化、保留情绪和冲突、避免硬翻、专有名词一致。
- 输出 Translation 实体符合 Spec §4.4：translation_id、segment_id、target_language、text、style、model、prompt_version、status、edited_by、updated_at、active。
- 对过长、疑似直译、缺失翻译、供应商失败、限流等生成 quality_flags 或错误码。
- 不覆盖 `locked=true` 的 Segment 对应人工编辑译文；同一 segment + target_language 多版本只允许一个 active（Spec §4.3、§4.4、§6）。
- 翻译 JSON 路径遵守 Spec §8：`projects/{project_id}/translations/{language}.json`。
- 边界：只做翻译与质量提示；不做 ASR、字幕文件生成、TTS、混音或打包。

## 输入

- 依赖的接口：
  - Spec §6 Skill 调用契约。
  - `packages/shared-types` 的 Segment、Translation、Translation Adapter、错误码、语言代码类型。
  - LLM Adapter（Spec §11.2）：DeepSeek 默认实现，mock 实现用于测试。
  - 对象存储端口：可选写入翻译 JSON。
  - Prompt 配置端口：读取 prompt_version、style、目标语言区域配置。
- 依赖的数据表：
  - 逻辑读取 `segments` / `segment_versions`。
  - 逻辑读取 `speakers` 作为角色语气上下文。
  - 逻辑写入 `translations` / `translation_versions`。
  - 逻辑关联 `skill_runs`：记录 provider、model、tokens、error。

## 产出

- `localization.translate` Skill 实现。
- DeepSeek/LLM Adapter 和 Prompt 模板管理。
- 翻译批处理与按目标语言循环策略。
- 质量检查：
  - 空译文。
  - 过长译文。
  - 目标语言缺失。
  - provider 限流或不可用。
- 单元测试和集成测试：
  - Translation Adapter 请求/响应映射。
  - active version 切换。
  - locked segment 不覆盖。
  - quality_flags 生成。
  - provider 失败映射到 Spec §12 错误码。

## 验收标准

- [ ] 输入输出符合 Spec §6 和 Spec §11.2。
- [ ] 支持目标语言 `en-US`、`zh-CN`、`es-ES`、`pt-BR`，语言代码遵守 Spec §3。
- [ ] 生成的 Translation 符合 Spec §4.4，并记录 model、prompt_version、style。
- [ ] 同一 segment + target_language 多版本只允许一个 active，人工编辑版本不被自动覆盖。
- [ ] provider 失败返回 `TRANSLATION_FAILED`、`PROVIDER_RATE_LIMITED` 或 `PROVIDER_UNAVAILABLE`（Spec §12）。
- [ ] usage 记录 provider、model、tokens、cost 字段，供 SkillRun 持久化（Spec §6）。
- [ ] 翻译 JSON 路径符合 Spec §8。

## 备注

- MVP 不要求自动质量报告，但应返回足够的 quality_flags 给进度页和校对页。
- Prompt 内容可以版本化；修改 prompt 必须产生新的 prompt_version。
