# 项目记忆 · video-multisrt-multi-hls

> 创建：2026-06-30 | 最后更新：2026-06-30 | 工作流：Jarvis 5 阶段

## 基本信息
- 英文名：video-multisrt-multi-hls
- 中文名：AI 短剧多语种翻译与音轨外切平台
- GitHub：https://github.com/pengcong2020520/video-multisrt-multiHLS.git
- 项目目录：`~/jarvis/projects/video-multisrt-multi-hls/`
- 用户文档来源：`~/多语种多音轨外切/`（6 份文档：BRD/PRD/TECH_SPEC/ARCHITECTURE/AGENT_SKILL_ARCHITECTURE/README）

## 当前阶段
**阶段③ 模块化开发 — 编排拆解已完成，待启动开发。**

## 文档状态（全部就绪）
- docs/brd.md ✅
- docs/prd.md ✅
- docs/spec.md ✅ **FROZEN**（用户自带，不可改）
- docs/architecture.md ✅
- docs/agent-skill-architecture.md ✅
- docs/original.md ✅（索引页）

## Git 状态（已解决）
- 认证方式：SSH deploy key（ed25519），走 ssh.github.com:443 端口
- ~/.ssh/config 已配好 GitHub SSH over 443
- remote: `git@github.com:pengcong2020520/video-multisrt-multiHLS.git`
- 3 个 commit 已推送：
  - `67d5a22` chore: scaffold
  - `48d28b9` docs: import (Spec FROZEN)
  - `b3b4d61` tasks: 9 module task cards + summary
- `git push origin main` 可直接使用，无需输密码

## 阶段③ 编排结果

### 模块拆解（9 个模块）
| # | 模块 | 代码目录 | 复杂度 | 执行工具 | 任务卡 |
|---|---|---|---|---|---|
| 1 | shared-types | `packages/shared-types` | **simple** | Claude Code (GLM) | tasks/packages-shared-types.md |
| 2 | apps/api | `apps/api` | complex | Codex | tasks/apps-api.md |
| 3 | agent-runtime | `packages/agent-runtime` | complex | Codex | tasks/packages-agent-runtime.md |
| 4 | skills/media | `packages/skills/media` | complex | Codex | tasks/packages-skills-media.md |
| 5 | skills/asr | `packages/skills/asr` | complex | Codex | tasks/packages-skills-asr.md |
| 6 | skills/localization | `packages/skills/localization` | complex | Codex | tasks/packages-skills-localization.md |
| 7 | skills/voice | `packages/skills/voice` | complex | Codex | tasks/packages-skills-voice.md |
| 8 | skills/packaging | `packages/skills/packaging` | complex | Codex | tasks/packages-skills-packaging.md |
| 9 | apps/web | `apps/web` | complex | Codex | tasks/apps-web.md |

### 建议开发顺序
1. **shared-types**（契约基线，GLM 做）— 先固化实体/状态/错误码/API DTO/Skill Schema
2. **apps/api 骨架**（Codex）— 数据库表/Repository/Spec §7 API 路由空实现/鉴权审计
3. **agent-runtime**（Codex）— 固定模板/Run Context/SkillRun 记录/人工暂停
4. **skills/media + skills/asr**（Codex 并行）— 打通上传→Segment 前半链路
5. **skills/localization**（Codex）— DeepSeek 翻译 + 短剧本地化
6. **apps/web 前半**（Codex）— 上传/进度/校对页
7. **skills/voice**（Codex）— TTS 分段/音色映射
8. **skills/packaging**（Codex）— 字幕/混音/manifest/zip
9. **apps/web 收口**（Codex）— 预览/下载页 + Spec §14 验收

### 分派策略
- **第 1 步**（可并行）：GLM 做 shared-types + Codex 做 api 骨架
- **第 2 步**（可并行）：Codex 做 agent-runtime + Codex 做 media + Codex 做 asr
- 后续按依赖关系逐步推进

### 技术栈
- 音视频：FFmpeg
- 声源分离：Demucs
- ASR：faster-whisper / WhisperX
- 翻译：DeepSeek（LLM 适配器，可切换）
- TTS：MiniMax / 豆包（Provider 适配器，可切换）
- 前端：Web（自定义播放器，VTT + 独立音轨）
- 任务队列：Redis Queue / Celery / BullMQ
- 数据库：PostgreSQL

## 模块开发进度
| 模块 | 状态 | 备注 |
|---|---|---|
| shared-types | ✅ 完成 | commit `8cfb40b`，46 单测全过；契约基线就绪 |
| apps/api | ✅ 完成 | commit `74663ee`，8 单测全过；Spec §7 全部 API + 模型 + 状态机 |
| agent-runtime | ✅ 完成 | Python package；固定模板、Run Context、SkillRun 编排、checkpoint、retry、局部重跑 |
| skills/media | 🔄 进行中 | 第 3 步，Codex |
| skills/asr | 🔄 进行中 | 第 3 步，Codex |
| skills/localization | ⬜ 未开始 | 第 4 步，Codex |
| apps/web | ⬜ 未开始 | 第 5/8 步，Codex |
| skills/voice | ⬜ 未开始 | 第 6 步，Codex |
| skills/packaging | ⬜ 未开始 | 第 7 步，Codex |

## 集成验收主线（Spec §14）
- Case 1：中文 2 分钟 → en-US，生成 VTT/SRT + 英文混合音轨，Web 可切换
- Case 2：英文 1 分钟 → es-ES，人声替换音轨，保留 BGM，下载包
- Case 3：修改 segment 译文 → 局部重跑 TTS → 重新混音 → 预览验证

## 关键约束
- Spec FROZEN，开发期间不可改
- 模块间只通过 Spec §6 Skill 契约 / §7 API 交互
- locked=true 的 Segment 不允许被自动覆盖
- 每次 Skill 调用生成新 SkillRun，不覆盖历史
- 模型 API key 不暴露前端
- MVP 用固定编排模板，不做 Agent 自主规划

## 下一步行动
→ shared-types 已完成（契约基线）。后续模块按建议顺序推进：
  apps/api 骨架 → agent-runtime → skills/media + skills/asr → ...
→ shared-types 消费方式：`import { ... } from '@video-multisrt/shared-types'`，
  先 `npm run build` 产出 dist；类型/Schema/枚举/路径函数见 src/index.ts。
  字段缺口先在此包按 Spec 扩展，再消费（任务卡备注）。
