# 模块任务卡 · packages/skills/media

> 阶段③ 分配给模块 Agent 的工作单元。一卡一模块。
> 关联：`docs/spec.md`（FROZEN）、`docs/architecture.md`、`docs/agent-skill-architecture.md`

## 归属

- 模块：packages/skills/media
- 负责 Agent：module-developer
- 代码目录：`packages/skills/media`
- 复杂度：complex

## 任务范围

- 实现媒体处理 Skill，覆盖 Agent+Skill 架构 §4：
  - `media.probe`
  - `media.extract_audio`
  - `audio.separate_sources`
- 使用 FFmpeg 完成视频探测、音频提取、格式转换，符合架构文档 §6.1。
- 使用 Demucs 或可替换 Source Separation Adapter 完成人声/背景音分离，符合架构文档 §6.2 与 Spec §11.4。
- 产出 Spec §4.2 MediaAsset 类型：
  - `source_audio`
  - `source_vocal`
  - `background_audio`
- 遵守文件命名规范（Spec §8）：
  - `projects/{project_id}/source/source.wav`
  - `projects/{project_id}/separation/vocals.wav`
  - `projects/{project_id}/separation/background.wav`
- 校验输入视频边界：MP4/MOV 优先、1-3 分钟建议、无音轨报 `NO_AUDIO_TRACK`、不支持格式报 `INVALID_VIDEO`、过长报 `VIDEO_TOO_LONG`（Spec §2、§12、PRD §3.2）。
- 边界：只实现媒体类 Skill；不做 ASR、翻译、TTS、字幕或打包；不删除 source_video 或上游资产。

## 输入

- 依赖的接口：
  - Spec §6 Skill 调用契约。
  - `packages/shared-types` 的 Skill 输入输出类型、MediaAsset 类型、错误码。
  - 对象存储端口：读取 source_video/source_audio，写入 source_audio/source_vocal/background_audio。
  - 可替换适配器端口：FFmpeg Probe/Extract、Source Separation Adapter（Spec §11.4）。
- 依赖的数据表：
  - 逻辑读写 `media_assets`：source_video、source_audio、source_vocal、background_audio。
  - 逻辑关联 `skill_runs`：由 Runtime/Worker 记录本 Skill 的输入输出引用。
  - 逻辑更新 `projects.duration_ms`：由 `media.probe` 输出元信息后交由 API/Runtime 持久化。

## 产出

- Skill 实现：
  - `media.probe`：输入 source_video asset，输出 duration_ms、format、codec、has_audio、audio_stream metadata、quality_flags。
  - `media.extract_audio`：输入 source_video asset，输出 source_audio asset。
  - `audio.separate_sources`：输入 source_audio asset，输出 source_vocal/background_audio assets 和 quality_score。
- FFmpeg 命令封装和错误映射。
- Source Separation Adapter 默认实现与 mock 实现。
- 单元测试和集成测试：
  - ffprobe 输出解析。
  - 无音轨/过长/不支持格式错误映射。
  - 文件路径生成符合 Spec §8。
  - source separation 成功和失败响应符合 Spec §6。

## 验收标准

- [ ] 所有 Skill 输入输出符合 Spec §6 request/response 格式。
- [ ] `media.probe` 能识别视频时长、格式、音轨并输出 `duration_ms`，无音轨时报 `NO_AUDIO_TRACK`（Spec §4.1、§4.2、§12）。
- [ ] `media.extract_audio` 生成 `source_audio` MediaAsset，不覆盖 source_video（Spec §4.2、§6）。
- [ ] `audio.separate_sources` 生成 `source_vocal` 和 `background_audio` MediaAsset，并返回 quality_score/quality_flags（Spec §4.2、§11.4）。
- [ ] 文件对象路径符合 Spec §8。
- [ ] FFmpeg/Demucs provider 可替换，不把 provider 细节暴露到 Runtime 模板。
- [ ] 失败时不删除上游资产，返回 Spec §12 对应错误码。

## 备注

- MVP 允许声源分离质量不完美，但必须保留质量提示。
- Demucs 可先作为默认本地基线，商业 API 作为后续适配器，不写死业务逻辑。
