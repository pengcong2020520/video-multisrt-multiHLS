# 模块任务卡 · apps/web

> 阶段③ 分配给前端 Agent 的工作单元。一卡一模块。
> 关联：`docs/spec.md`（FROZEN）、`docs/prd.md`、`docs/architecture.md`、`docs/agent-skill-architecture.md`

## 归属

- 模块：apps/web
- 负责 Agent：frontend-developer
- 代码目录：`apps/web`
- 复杂度：complex

## 任务范围

- 实现内部运营 Web 管理端，覆盖 PRD §3.1-§3.7 页面：项目列表、上传配置、处理进度、校对编辑、网页预览、结果下载、Skill 配置查看。
- 对接 Spec §7 API：
  - §7.1 `POST /api/projects` 创建项目并获取上传 URL。
  - §7.2 `POST /api/projects/{project_id}/process` 提交处理。
  - §7.3 `GET /api/agent-runs/{run_id}` 展示 AgentRun、SkillRun、checkpoint、quality_flags。
  - §7.4 `POST /api/agent-runs/{run_id}/continue` 在 proofreading 后继续。
  - §7.5 `GET /api/projects/{project_id}` 展示项目、任务、资产、语言。
  - §7.6 `GET /api/projects/{project_id}/segments` 展示句段、译文、TTS 状态。
  - §7.7 `PATCH /api/projects/{project_id}/segments/{segment_id}` 保存原文/译文/时间轴/说话人/锁定状态。
  - §7.8 `POST /api/projects/{project_id}/generate` 触发目标语言生成或局部重跑。
  - §7.9 `GET /api/projects/{project_id}/manifest` 获取播放器 manifest。
  - §7.10 `POST /api/projects/{project_id}/packages` 请求结果包。
- 实现自定义播放器，遵守架构文档 §7：视频使用原画面轨，字幕使用 WebVTT 自定义渲染，目标语言音轨使用独立 audio/Web Audio 同步切换。
- 实现校对编辑体验，覆盖 PRD §3.4：按目标语言切换、修改译文、修改说话人/音色、合并/拆分入口、单句试听入口、单句或单语言重跑入口。
- 展示状态和错误，映射 Spec §5 Project/Task/Agent Run 状态与 Spec §12 错误码。
- 边界：只调用 Spec §7 HTTP API；不直接访问数据库、对象存储私有路径、Skill Runtime、模型供应商或服务端密钥。

## 输入

- 依赖的接口：
  - `apps/api` 的 Spec §7 HTTP API。
  - `packages/shared-types` 导出的 API DTO、实体枚举、状态枚举、错误码、Manifest 类型。
- 依赖的数据表：
  - 不直接依赖数据库表；通过 API 间接读取 Project、MediaAsset、Segment、Translation、Speaker、TTSJob、AgentRun、SkillRun、SkillDefinition。

## 产出

- Web 应用代码与页面路由。
- API Client 和前端类型绑定，字段与 `packages/shared-types` 保持一致。
- 上传配置表单、进度视图、校对表格、播放器、下载列表、Skill 配置查看页。
- 前端单元测试和关键交互测试：
  - API Client 参数和错误映射。
  - 校对编辑保存、locked 提示、stale 下游产物提示。
  - 播放器字幕/音轨切换时 currentTime 同步。
  - 进度页状态和错误码展示。

## 验收标准

- [ ] 上传配置页能创建项目、上传视频、提交 `subtitle_draft` 或 `full_dubbing` 模板（Spec §7.1、§7.2）。
- [ ] 处理进度页能展示 AgentRun、SkillRun、当前 checkpoint、quality_flags 和失败错误（Spec §4.8、§4.9、§7.3、§12）。
- [ ] 校对页能编辑 Segment/Translation/Speaker/locked，并通过 PATCH 保存；保存后可继续 waiting_human run（Spec §4.3、§4.4、§4.5、§7.4、§7.7）。
- [ ] 生成页能按语言或指定 segment 发起 `subtitle`、`tts`、`mix` 重跑（Spec §7.8）。
- [ ] 预览页使用 Manifest 渲染视频、字幕和独立音轨，支持原音轨/目标语言音轨切换（Spec §4.7、§7.9、架构 §7）。
- [ ] 下载页能展示字幕、音轨、manifest、zip 并请求重新打包（Spec §7.10、PRD §3.6）。
- [ ] 前端不展示模型 API key、对象存储私有 URI 或供应商私有 endpoint（Spec §13）。
- [ ] 测试覆盖核心用户旅程：上传配置、校对保存、继续 Run、预览切换、结果下载。

## 备注

- UI 以运营效率为优先，不做营销落地页。
- 前端合并/拆分句段可以先实现交互和 API 调用入口；实际版本和下游 stale 语义由 API 负责。
