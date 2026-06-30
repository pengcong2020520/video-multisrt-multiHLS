# CLAUDE.md · video-multisrt-multi-hls

> 本项目的 Claude Code 工作指令。任何 Agent 在此项目工作前必读。

## 项目
- 英文名：video-multisrt-multi-hls
- 创建：2026-06-30
- 工作流：遵循 `~/jarvis/playbook.md` 的 5 阶段方法论

## 当前阶段
① 想法 → ② 文档 → ③ 开发 → ④ 收尾　（在项目记忆里标注当前位置）

## 铁律（所有 Agent）
1. **Spec 不可改**：`docs/spec.md` 是契约。开发期间严格遵守其架构、接口契约、数据库设计、开发规范。需要改 Spec → 停下回阶段② 修订（版本+1）再继续。
2. **模块化守边界**：每个模块一个 Agent，只动自己模块目录（`src/modules/<模块>/`）；模块间仅通过 Spec §4 接口契约交互；**禁止越界改他人代码**。
3. **遵循开发规范**：代码风格/测试/提交/错误处理一律按 Spec §5。

## 角色（.claude/agents/）
- `orchestrator` —— 拆模块、出任务卡、分派、集成、守 Spec（不写业务代码）
- `module-developer` —— 后端/逻辑模块开发（每模块一个）
- `frontend-developer` —— 前端
- `ui-designer` —— UI 视觉（复用 skill / GPT image 2）

## 关键路径
- 文档：`docs/`（original / prd / requirements / spec）
- 任务卡：`tasks/`
- 代码：`src/{modules,frontend}/`
- 设计资产：`design/`
- **项目记忆**：`memory/video-multisrt-multi-hls.md`（先读、勤更新、与其他项目隔离）

## 收尾
项目完成后，写「设计理念+技术架构」总览到 `~/my_note/projects/video-multisrt-multi-hls.md`（模板 `~/jarvis/templates/obsidian-architecture.md`）。
