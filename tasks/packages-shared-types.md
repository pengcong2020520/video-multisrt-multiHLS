# 模块任务卡 · packages/shared-types

> 阶段③ 分配给模块 Agent 的工作单元。一卡一模块。
> 关联：`docs/spec.md`（FROZEN）、`docs/agent-skill-architecture.md`

## 归属

- 模块：packages/shared-types
- 负责 Agent：module-developer
- 代码目录：`packages/shared-types`
- 复杂度：simple

## 任务范围

- 固化全仓共享契约，覆盖 Spec §3-§13：
  - 语言代码（Spec §3）。
  - 核心实体：Project、MediaAsset、Segment、Translation、Speaker、TTSJob、Manifest、AgentRun、SkillRun、SkillDefinition（Spec §4）。
  - 状态枚举：Project Status、Task Status、Agent Run Status、Task Type（Spec §5）。
  - Skill 调用契约 request/success/failure（Spec §6）。
  - API DTO（Spec §7）。
  - 对象存储路径模板（Spec §8）。
  - Adapter 输入输出类型：ASR、Translation、TTS、Source Separation（Spec §11）。
  - 错误码（Spec §12）。
- 提供运行时 Schema 校验，供 API、Runtime、Skill 和 Web 复用。
- 提供稳定导出，不引入业务模块依赖。
- 边界：只定义类型、Schema、常量和纯函数；不访问数据库、对象存储、队列、模型或网络。

## 输入

- 依赖的接口：
  - 无业务模块依赖。
  - 可依赖通用 Schema/validation 库和 TypeScript 工具链。
- 依赖的数据表：
  - 不直接依赖数据库表。
  - 需为下列表的字段提供类型/Schema：projects、media_assets、segments、translations、speakers、tts_jobs、agent_runs、skill_runs、skill_definitions、tasks、versions、audit_logs。

## 产出

- TypeScript 类型、枚举、Schema 和工具函数。
- API DTO：
  - `CreateProjectRequest/Response`
  - `ProcessProjectRequest/Response`
  - `GetAgentRunResponse`
  - `ContinueAgentRunRequest`
  - `GetProjectResponse`
  - `GetSegmentsResponse`
  - `PatchSegmentRequest`
  - `GenerateProjectRequest`
  - `ManifestResponse`
  - `CreatePackageRequest/Response`
- Skill Contract 类型：
  - `SkillRequest<TInput, TConfig>`
  - `SkillSuccessResponse<TOutput>`
  - `SkillFailureResponse`
  - `SkillResponse`
- Skill-specific input/output 类型：
  - media/asr/localization/voice/packaging。
- 路径生成纯函数：
  - source、separation、asr、translations、subtitles、tts、audio、preview、packages。
- 单元测试：
  - 枚举值完整性。
  - Schema 接受 Spec 示例。
  - Schema 拒绝非法语言、非法状态、非法时间轴、未知错误码。
  - 路径生成符合 Spec §8。

## 验收标准

- [ ] Spec §3 语言代码被枚举或 Schema 限制，支持 `zh-CN`、`en-US`、`es-ES`、`es-MX`、`pt-BR`、`auto` 的语义边界。
- [ ] Spec §4 核心实体都有类型和运行时 Schema。
- [ ] Spec §5 状态和 Task Type 都有枚举，且值与文档一致。
- [ ] Spec §6 Skill request/response 类型支持泛型输入输出、usage、assets、quality_flags、error。
- [ ] Spec §7 API DTO 字段完整，供 Web 与 API 共用。
- [ ] Spec §8 路径生成函数输出与文档一致。
- [ ] Spec §11 Adapter 类型完整，供 Skill provider 适配器实现。
- [ ] Spec §12 错误码完整，未知错误码不能通过 Schema 校验。
- [ ] 本包不导入 `apps/*` 或其他 `packages/*` 的业务实现。

## 备注

- 这是所有模块的先置任务；后续模块发现字段缺口时，应先在此包按 Spec 扩展，再消费类型。
- 可以添加扩展字段，但不能改变 Spec 已定义字段的核心语义。
