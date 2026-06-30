# 模块任务卡 · apps/api

> 阶段③ 分配给模块 Agent 的工作单元。一卡一模块。
> 关联：`docs/spec.md`（FROZEN）、`docs/architecture.md`、`docs/prd.md`

## 归属

- 模块：apps/api
- 负责 Agent：module-developer
- 代码目录：`apps/api`
- 复杂度：complex

## 任务范围

- 实现 Spec §7 最小 API 的服务端语义：
  - §7.1 创建项目并生成上传 URL。
  - §7.2 提交处理并创建 AgentRun。
  - §7.3 查询 AgentRun 与 SkillRun。
  - §7.4 保存人工编辑后继续 AgentRun。
  - §7.5 查询项目详情。
  - §7.6 查询句段、active translation、TTSJob。
  - §7.7 更新句段和译文。
  - §7.8 生成或重跑目标语言。
  - §7.9 获取播放器 Manifest。
  - §7.10 请求下载结果包。
- 维护 Spec §4 核心实体的持久化边界：Project、MediaAsset、Segment、Translation、Speaker、TTSJob、Manifest 引用、AgentRun、SkillRun、SkillDefinition。
- 维护 Spec §5 状态机：Project Status、Task Status、Agent Run Status、Task Type。
- 处理对象存储授权、资产索引和文件命名规范（Spec §8）。
- 接收并校验人工编辑：Segment 时间轴、locked、Translation edited_by、下游字幕/TTS/mix stale 标记（Spec §4.3、§4.4、§7.7）。
- 调用 `packages/agent-runtime` 的公开接口创建、继续、重跑 Run；API 服务不直接调用具体 Skill。
- 落实安全要求（Spec §13）：服务端保存模型密钥，下载 URL 带过期时间或鉴权，记录上传/编辑/生成/下载审计。
- 边界：对外只暴露 Spec §7 API；对内只调用 Agent Runtime 接口和 Repository/Object Storage 端口；不执行 FFmpeg、ASR、翻译、TTS、混音。

## 输入

- 依赖的接口：
  - `packages/shared-types` 的实体、DTO、状态、错误码和 Schema。
  - `packages/agent-runtime` 的 Run 创建、继续、重跑、查询聚合接口。
  - 对象存储端口：生成上传 URL、生成下载 URL、保存/读取资产引用。
  - 数据库/Repository 端口。
- 依赖的数据表：
  - `projects`
  - `media_assets`
  - `segments`
  - `segment_versions` 或等价版本表
  - `translations`
  - `translation_versions` 或 active 标记
  - `speakers`
  - `tts_jobs`
  - `agent_runs`
  - `skill_runs`
  - `skill_definitions`
  - `tasks`
  - `versions`
  - `audit_logs`

## 产出

- API 服务代码、路由、校验、错误处理和鉴权/审计中间件。
- 数据库迁移或 Schema 定义，字段覆盖 Spec §4、§5、§12、§13 的核心语义。
- Repository/Object Storage/Agent Runtime 适配层。
- OpenAPI 或等价接口文档，字段与 `packages/shared-types` 一致。
- 单元测试和集成测试：
  - DTO 校验和错误码。
  - Segment/Translation 更新与 locked/stale 规则。
  - 创建 Run、继续 Run、局部重跑。
  - Manifest 和下载包 URL 授权。

## 验收标准

- [ ] Spec §7.1-§7.10 API 全部可用，返回字段与 Spec 示例语义一致。
- [ ] 创建项目后产生 Project，上传完成后可登记 source_video MediaAsset（Spec §4.1、§4.2）。
- [ ] 提交处理能创建 AgentRun，并将模板限制在 `subtitle_draft`、`full_dubbing`、`rerun_segments`、`package_only`（Spec §4.8、§7.2、§7.8）。
- [ ] 查询 Run 能返回 AgentRun、SkillRun、checkpoint 和 quality_flags（Spec §4.8、§4.9、§7.3）。
- [ ] PATCH Segment 遵守 start_ms < end_ms、edited_by、locked 和下游 stale 标记规则（Spec §4.3、§4.4、§7.7）。
- [ ] 继续 Run 前必须保存用户编辑，且只允许 `waiting_human` 状态继续（Spec §7.4）。
- [ ] 生成或重跑目标语言能正确区分 `language`、`segments`、`package` scope（Spec §7.8）。
- [ ] Manifest 与下载 URL 不暴露私有 URI，URL 有鉴权或过期时间（Spec §4.7、§7.9、§13）。
- [ ] 失败响应使用 Spec §12 错误码并记录审计。

## 备注

- API 是 Web 与 Runtime 的唯一业务入口；不要让前端直接调用 Runtime 或 Skill。
- 数据库表名可按实现调整，但必须能表达本卡列出的实体和版本语义。
