# 模块任务卡 · packages/skills/packaging

> 阶段③ 分配给模块 Agent 的工作单元。一卡一模块。
> 关联：`docs/spec.md`（FROZEN）、`docs/architecture.md`、`docs/agent-skill-architecture.md`

## 归属

- 模块：packages/skills/packaging
- 负责 Agent：module-developer
- 代码目录：`packages/skills/packaging`
- 复杂度：complex

## 任务范围

- 实现打包与交付类 Skill，覆盖 Agent+Skill 架构 §4：
  - `subtitle.generate`
  - `audio.stitch_vocals`
  - `audio.mix`
  - `package.manifest`
  - `package.zip`
  - 可选 `quality.check`
- 字幕生成遵守 Spec §9：
  - SRT 使用 Segment start_ms/end_ms。
  - 文本使用 active Translation。
  - 单条字幕建议不超过两行。
  - WebVTT 用于网页播放器，不放业务私有 JSON。
- 音频生成遵守 Spec §10：
  - TTS 分段音频拼接前统一采样率和声道。
  - 以 segment.start_ms 作为放置起点。
  - TTS 短于 Segment 时补静音。
  - TTS 长于 Segment 时优先质量提示或依赖上游调速，不做跨句复杂动态压缩。
  - `background_audio` 作为底轨，`target_vocal` 按时间轴叠加，输出 `target_mix_audio`，保留 `source_audio` 作为原音轨切换。
- 使用 FFmpeg 完成人声拼接、混音、可选预览 MP4，符合架构文档 §6.1、§7.3。
- 生成 Manifest 符合 Spec §4.7 与 §7.9，供 Web 播放器切换字幕/音轨。
- 生成下载包符合 PRD §3.6 与 Spec §7.10。
- 文件路径遵守 Spec §8：
  - `projects/{project_id}/subtitles/{language}.srt`
  - `projects/{project_id}/subtitles/{language}.vtt`
  - `projects/{project_id}/audio/{language}.vocal.wav`
  - `projects/{project_id}/audio/{language}.mix.m4a`
  - `projects/{project_id}/preview/{language}.mp4`
  - `projects/{project_id}/packages/{version_id}.zip`
- 边界：只消费上游资产引用和结构化数据；不做 ASR、翻译或 TTS provider 调用。

## 输入

- 依赖的接口：
  - Spec §6 Skill 调用契约。
  - `packages/shared-types` 的 Segment、Translation、TTSJob、MediaAsset、Manifest、错误码类型。
  - 对象存储端口：读取 TTS 分段音频、background_audio、source_audio/source_video，写入字幕、target_vocal、target_mix_audio、preview_video、package_zip、manifest。
  - FFmpeg Adapter：音频拼接、采样率/声道统一、混音、可选预览 MP4。
- 依赖的数据表：
  - 逻辑读取 `segments` / `segment_versions`。
  - 逻辑读取 active `translations` / `translation_versions`。
  - 逻辑读取 `tts_jobs`。
  - 逻辑读取/写入 `media_assets`。
  - 逻辑读取/写入 `versions`。
  - 逻辑关联 `skill_runs`。

## 产出

- Skill 实现：
  - `subtitle.generate`：输出 `subtitle_srt`、`subtitle_vtt`。
  - `audio.stitch_vocals`：输出 `target_vocal`。
  - `audio.mix`：输出 `target_mix_audio`，可选 `preview_video`。
  - `package.manifest`：输出 Manifest JSON。
  - `package.zip`：输出 `package_zip`。
- SRT/WebVTT 生成器。
- FFmpeg 音频处理封装。
- Zip 打包器和 manifest URL 生成逻辑。
- 单元测试和集成测试：
  - 时间戳格式化。
  - active translation 选择。
  - TTS 音频按 segment.start_ms 对齐。
  - 混音输出资产登记。
  - Manifest 结构校验。
  - zip 内容清单。

## 验收标准

- [ ] `subtitle.generate` 生成 SRT/VTT，文本来自 active Translation，时间轴来自 Segment（Spec §4.3、§4.4、§9）。
- [ ] `audio.stitch_vocals` 按 Segment 时间轴拼接 TTS 分段音频，生成 `target_vocal`（Spec §10.1、§10.2）。
- [ ] `audio.mix` 使用 `background_audio` 作为底轨，叠加 `target_vocal`，生成 `target_mix_audio` 并保留原音轨切换能力（Spec §10.3）。
- [ ] `package.manifest` 输出结构符合 Spec §4.7，URL 使用可访问的授权/公开代理地址，不暴露私有 URI（Spec §13）。
- [ ] `package.zip` 包含 PRD §3.6 要求的字幕、音轨、manifest 和可选中间资产。
- [ ] 文件路径符合 Spec §8。
- [ ] 失败时返回 `MIXING_FAILED`、`PACKAGE_FAILED` 或对应错误码，不删除上游产物（Spec §6、§12）。

## 备注

- Web 预览以 manifest + 独立音轨 + VTT 为主；多音轨 MP4 只作为下载或后处理增强产物。
- `quality.check` 可先作为聚合函数实现，返回 flags 给 Runtime，不阻塞主链路。
