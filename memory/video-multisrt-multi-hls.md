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
| skills/media | ✅ 完成 | 9 单测全过；FFmpeg probe/extract + Demucs separate_sources |
| skills/asr | ✅ 完成 | commit `f0e218f`，8 单测全过；transcribe + diarize + normalize_segments |
| skills/localization | ✅ 完成 | 7 单测全过；DeepSeek adapter + 短剧本地化 prompt |
| apps/web | ✅ 完成 | commit `5d41919`，40 文件 3592 行；7 页面 + 自定义播放器 + API client |
| skills/voice | ✅ 完成 | commit `06cf9bb`，6 单测全过；TTS adapter + voice mapping |
| skills/packaging | ✅ 完成 | commit `3634f2c`，6 单测全过；subtitle + stitch + mix + manifest + zip |

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

## 工作原则（用户要求严格执行）
1. **第一性原理**：每一步都从本质出发分析，不自以为是套模板。问"这步解决什么问题？数据从哪来到哪去？砍掉行不行？"
2. **对抗式审查**：每完成一个阶段，换挑刺者视角重新审视——边界检查、契约一致性、链路完整性、Spec 合规、安全盲区。发现问题立即修，不攒着。

## 下一步行动
→ E2E 测试进行中。已修 4 个运行时 bug，正在修第 5 个（文件路径不匹配：`storage/proj_xxx/` vs `storage/projects/proj_xxx/`）。
→ 修完后继续跑通：probe → extract → separate → ASR → translate → subtitle → TTS → mix → manifest → 预览

## 项目复盘经验（持续更新）

### ✅ 成功经验（可复用）

1. **Codex 编排拆模块效果好**：Codex CLI 读 Spec 后自主拆 9 个模块，每张任务卡精确到 Spec 章节号，复杂度标注准确。比人工拆更快更全面。
2. **Codex/Claude Code 分工并行**：simple 模块(shared-types)给 Claude Code(GLM) 做，complex 模块给 Codex 做。两者并行，15 分钟完成 shared-types，20 分钟完成 api。
3. **对抗式审查必须做**：9 个模块各自单测 95+ 全过，但拼在一起是空壳——NoopSkillRunner 没接线、持久化断裂、数据传递断裂。单测通过 ≠ 系统能跑通。
4. **每步 commit+push 到 GitHub**：出问题随时回滚，不怕改坏。开发过程中每次修复都立即推送。
5. **任务卡驱动开发**：每个模块有独立任务卡（tasks/*.md），Codex 读任务卡+Spec 后自主实现，产出质量高。
6. **Mock 优先的测试策略**：所有 skill 包用 Mock adapter，单测不依赖真实 FFmpeg/模型/API，跑得快（0.01s）。
7. **prompt 写入临时文件再 cat 传给 Codex**：避免 Unicode（§+CJK）被安全扫描拦截。

### ❌ 失败教训（要避免）

1. **模块间接线缺失**：9 个模块各自开发，但没人负责"接线"——CompositeSkillRunner、DatabaseResponsePersister、RunContext 数据传递都没有。**教训：编排者不仅要拆任务，还要定义模块间集成契约。**
2. **auto_execute=False 但没 worker**：runtime 创建 run 后 enqueue 到 Redis，但没有任何 worker 从队列消费。run 永远 pending。**教训：MVP 阶段用 auto_execute=True 同步执行，不要引入队列除非有 consumer。**
3. **SkillDefinition 未初始化**：registry 从 DB 查 SkillDefinition 但没人初始化。**教训：需要 allow_missing_defaults=True 或启动时 seed 默认 SkillDefinition。**
4. **storage_root 未注入到 skill config**：CompositeSkillRunner 没把 STORAGE_ROOT 环境变量传给 skill，导致 ffprobe 找不到文件。**教训：skill 需要的配置必须显式注入，不能假设环境变量自动可用。**
5. **文件路径不匹配**：DB 里 URI 是 `storage://private/projects/{pid}/source/source.mp4`，但测试脚本复制文件到 `storage/{pid}/source/source.mp4`（少了 `projects/` 层）。**教训：上传逻辑和存储路径必须严格对齐 Spec §8 规范。**
6. **TS/Python 类型各写各的**：shared-types(TS) 和 schemas.py(Python) 的字段可空性不一致。**教训：跨语言项目需要一份单一数据源(source of truth)定义类型契约。**
7. **uvicorn --timeout 不是有效参数**：导致服务启动失败。**教训：先验证 CLI 参数再写启动脚本。**
8. **upload_url PUT 404**：签名 URL 对应的上传路由不存在。**教训：storage 层的上传端点要和签名 URL 生成逻辑匹配。**

### 🔧 调试方法论

1. **加调试日志**：在关键路径加 print(flush=True)，看实际传了什么值。
2. **从第一性原理分析**：不走猜测，回到"数据从哪来？到哪去？谁依赖谁？"的本质问题。
3. **逐层排查**：先确认服务启动 → API 可达 → 数据库写入 → skill 执行 → 文件路径 → 业务逻辑。
4. **每次只改一个变量**：修复一个问题就重跑测试，不要攒多个修改一起测。
