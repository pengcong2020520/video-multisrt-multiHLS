> **Status: FROZEN** — 用户自带完整 Spec，直接进入阶段③开发。

# AI 短剧多语种翻译与音轨外切平台 TECH SPEC

## 1. 目标

定义 MVP 的最小技术接口、核心数据结构、任务状态机和模块边界，确保研发可以基于统一约束完成第一版 Web coding 和后端处理链路。

本 Spec 不追求一次性覆盖所有未来需求。实际开发中允许扩展字段，但不得破坏本文定义的核心语义。

## 2. 技术边界

### 2.1 系统能做

- 接收 1-3 分钟短剧视频上传。
- 生成原视频元信息。
- 拆出原始音频。
- 分离人声和背景音。
- 对原人声进行 ASR。
- 生成统一句段 segments。
- 调用 LLM 生成目标语言翻译。
- 允许人工编辑句段和译文。
- 调用 TTS 生成目标语言人声。
- 混合目标语言人声和原背景音。
- 生成字幕、音轨、预览文件和下载包。
- 网页预览时支持字幕和音轨切换。
- 通过 Agent Runtime 编排可复用 Skill，并记录每次 Skill Run。

### 2.2 系统不能承诺

- 不承诺唇形级同步。
- 不承诺完全去除原人声。
- 不承诺多人重叠对白准确识别。
- 不承诺无人工校对即可发布。
- 不承诺所有视频格式都支持。
- 不承诺任何单一模型供应商稳定可用。

## 3. 语言代码

统一使用 BCP 47 风格语言代码。

| 语言 | 代码 |
| --- | --- |
| 中文 | zh-CN |
| 英文 | en-US |
| 西语 | es-ES 或 es-MX |
| 葡语 | pt-BR |

MVP 默认：

- 源语言：zh-CN、en-US、auto。
- 目标语言：en-US、zh-CN、es-ES、pt-BR。

## 4. 核心实体

### 4.1 Project

```json
{
  "project_id": "proj_123",
  "name": "episode_01",
  "status": "processing",
  "source_language": "auto",
  "target_languages": ["en-US", "es-ES"],
  "duration_ms": 128000,
  "created_by": "user_001",
  "created_at": "2026-06-30T10:00:00Z",
  "updated_at": "2026-06-30T10:03:00Z"
}
```

### 4.2 MediaAsset

```json
{
  "asset_id": "asset_123",
  "project_id": "proj_123",
  "type": "source_video",
  "language": null,
  "uri": "s3://bucket/proj_123/source.mp4",
  "format": "mp4",
  "duration_ms": 128000,
  "size_bytes": 104857600,
  "checksum": "sha256:...",
  "created_at": "2026-06-30T10:00:00Z"
}
```

Asset type 枚举：

| type | 说明 |
| --- | --- |
| source_video | 原视频 |
| source_audio | 原始音频 |
| source_vocal | 分离后的原人声 |
| background_audio | 分离后的背景音 |
| subtitle_srt | SRT 字幕 |
| subtitle_vtt | WebVTT 字幕 |
| tts_segment_audio | 单句 TTS 音频 |
| target_vocal | 拼接后的目标语言人声 |
| target_mix_audio | 目标语言混合音轨 |
| preview_video | 预览 MP4 |
| package_zip | 下载包 |

### 4.3 Segment

Segment 是字幕、翻译和 TTS 的共同最小单位。

```json
{
  "segment_id": "seg_0001",
  "project_id": "proj_123",
  "index": 1,
  "start_ms": 1200,
  "end_ms": 3600,
  "speaker_id": "spk_1",
  "source_language": "zh-CN",
  "source_text": "你到底想怎么样？",
  "asr_confidence": 0.92,
  "locked": false,
  "quality_flags": []
}
```

规则：

- start_ms 必须小于 end_ms。
- segment 不应跨越过长静音。
- 默认单句建议 0.8-8 秒。
- 人工编辑后的 segment 需要记录版本。
- locked=true 的 segment 不允许被自动重写。

### 4.4 Translation

```json
{
  "translation_id": "tr_0001_en",
  "segment_id": "seg_0001",
  "target_language": "en-US",
  "text": "What exactly do you want from me?",
  "style": "short_drama_localized",
  "model": "deepseek-default",
  "prompt_version": "short_drama_v1",
  "status": "completed",
  "edited_by": null,
  "updated_at": "2026-06-30T10:05:00Z"
}
```

规则：

- text 是 TTS 和字幕的默认文本来源。
- 人工编辑后 edited_by 必须有值。
- 同一 segment + target_language 可以有多个版本，但只能有一个 active=true。

### 4.5 Speaker

```json
{
  "speaker_id": "spk_1",
  "project_id": "proj_123",
  "display_name": "Female Lead",
  "source_voice_sample_asset_id": "asset_voice_001",
  "target_voice_map": {
    "en-US": "voice_en_female_01",
    "es-ES": "voice_es_female_01"
  }
}
```

规则：

- speaker_id 可由系统自动生成，也可由用户手动调整。
- MVP 不要求识别真实人物身份。
- 声音克隆必须额外校验授权，不作为默认能力。

### 4.6 TTSJob

```json
{
  "tts_job_id": "tts_123",
  "project_id": "proj_123",
  "segment_id": "seg_0001",
  "target_language": "en-US",
  "text": "What exactly do you want from me?",
  "voice_id": "voice_en_female_01",
  "target_duration_ms": 2400,
  "speed": 1.0,
  "status": "completed",
  "output_asset_id": "asset_tts_0001",
  "actual_duration_ms": 2520,
  "provider": "minimax",
  "provider_task_id": "remote_123",
  "error": null
}
```

规则：

- target_duration_ms 来源于 segment 时长。
- TTS 可允许一定偏差，MVP 建议 <= 20%。
- 超出偏差时打 quality_flags，不强制失败。

### 4.7 Manifest

网页播放器使用 manifest 获取可播放资源。

```json
{
  "project_id": "proj_123",
  "version_id": "ver_001",
  "video": {
    "url": "https://cdn.example.com/proj_123/source.mp4",
    "duration_ms": 128000
  },
  "subtitles": [
    {
      "language": "zh-CN",
      "label": "中文原文",
      "format": "vtt",
      "url": "https://cdn.example.com/proj_123/source.zh-CN.vtt"
    },
    {
      "language": "en-US",
      "label": "English",
      "format": "vtt",
      "url": "https://cdn.example.com/proj_123/en-US.vtt"
    }
  ],
  "audio_tracks": [
    {
      "language": "source",
      "label": "原音轨",
      "url": "https://cdn.example.com/proj_123/source_audio.m4a"
    },
    {
      "language": "en-US",
      "label": "English Dub",
      "url": "https://cdn.example.com/proj_123/en-US.mix.m4a"
    }
  ],
  "downloads": [
    {
      "type": "package_zip",
      "label": "完整结果包",
      "url": "https://cdn.example.com/proj_123/package.zip"
    }
  ]
}
```

### 4.8 AgentRun

```json
{
  "run_id": "run_123",
  "project_id": "proj_123",
  "version_id": "ver_001",
  "template": "full_dubbing",
  "status": "running",
  "current_step": "localization.translate",
  "source_language": "auto",
  "target_languages": ["en-US", "es-ES"],
  "created_by": "user_001",
  "created_at": "2026-06-30T10:01:00Z",
  "updated_at": "2026-06-30T10:03:00Z"
}
```

template 枚举：

| template | 说明 |
| --- | --- |
| subtitle_draft | 只生成 ASR、翻译和字幕初稿 |
| full_dubbing | 生成字幕、TTS、混音和下载包 |
| rerun_segments | 局部重跑指定句段 |
| package_only | 只重新生成 manifest 或下载包 |

### 4.9 SkillRun

```json
{
  "skill_run_id": "skillrun_123",
  "run_id": "run_123",
  "project_id": "proj_123",
  "skill_name": "localization.translate",
  "skill_version": "1.0.0",
  "status": "succeeded",
  "target_language": "en-US",
  "started_at": "2026-06-30T10:03:00Z",
  "finished_at": "2026-06-30T10:03:30Z",
  "input_refs": ["segver_001"],
  "output_refs": ["trver_en_001"],
  "provider": "deepseek",
  "model": "deepseek-default",
  "error": null
}
```

规则：

- 每次 Skill 调用必须生成 SkillRun。
- input_refs 和 output_refs 只记录引用，不保存大型内容。
- 失败时必须记录 error.code 和 error.message。
- 重试必须生成新的 SkillRun，不覆盖历史记录。

### 4.10 SkillDefinition

```json
{
  "skill_name": "voice.synthesize",
  "skill_version": "1.0.0",
  "enabled": true,
  "default_provider": "minimax",
  "input_schema": "VoiceSynthesizeInput",
  "output_schema": "VoiceSynthesizeOutput",
  "timeout_seconds": 120,
  "retry_limit": 2
}
```

规则：

- SkillDefinition 由内部管理员维护。
- 前端只能查看可展示字段，不能读取 API key。
- 同一 skill_name 可以存在多个版本，但生产默认版本必须明确。

## 5. 任务状态机

### 5.1 Project Status

| 状态 | 说明 |
| --- | --- |
| draft | 已创建但未上传完成 |
| uploaded | 上传完成 |
| planning | Agent Runtime 正在生成执行计划 |
| processing | 自动处理中 |
| proofreading | 等待人工校对 |
| generating | 正在生成 TTS/混音/打包 |
| completed | 完成 |
| failed | 失败 |
| archived | 已归档 |

### 5.2 Task Status

| 状态 | 说明 |
| --- | --- |
| pending | 等待执行 |
| running | 执行中 |
| succeeded | 成功 |
| failed | 失败 |
| canceled | 已取消 |
| retrying | 等待重试 |

### 5.3 Agent Run Status

| 状态 | 说明 |
| --- | --- |
| pending | 等待开始 |
| planning | 生成执行计划 |
| running | 执行中 |
| waiting_human | 等待人工校对或确认 |
| succeeded | 成功 |
| failed | 失败 |
| canceled | 已取消 |

### 5.4 Task Type

```json
[
  "probe_media",
  "extract_audio",
  "separate_sources",
  "asr",
  "segment_normalize",
  "translate",
  "generate_subtitle",
  "tts",
  "stitch_target_vocal",
  "mix_audio",
  "package_outputs"
]
```

规则：

- 每个 task 必须绑定 project_id。
- Agent 编排型 task 必须绑定 run_id。
- 语言相关 task 必须绑定 target_language。
- task 失败必须记录 error_code 和 error_message。
- task 可重试，但重试次数由配置控制。

## 6. Skill 调用契约

Skill 是 Agent Runtime 的最小可复用能力单元。所有 Skill 都必须使用结构化输入输出。

Request:

```json
{
  "skill_name": "localization.translate",
  "skill_version": "1.0.0",
  "project_id": "proj_123",
  "run_id": "run_123",
  "input": {},
  "config": {},
  "idempotency_key": "run_123:localization.translate:en-US:v1"
}
```

Success Response:

```json
{
  "status": "succeeded",
  "outputs": {},
  "assets": [],
  "quality_flags": [],
  "usage": {
    "provider": "deepseek",
    "model": "deepseek-default",
    "tokens": 1200,
    "cost": null
  },
  "error": null
}
```

Failure Response:

```json
{
  "status": "failed",
  "outputs": {},
  "assets": [],
  "quality_flags": [],
  "usage": {},
  "error": {
    "code": "TRANSLATION_FAILED",
    "message": "Provider request failed"
  }
}
```

规则：

- Skill 不直接决定下一步流程，下一步由 Agent Runtime 决定。
- Skill 不删除上游资产。
- Skill 不能覆盖 locked segment。
- Skill 所需密钥由服务端注入，不能由前端传入。

## 7. 最小 API

以下 API 仅定义语义，不绑定具体框架。

### 7.1 创建项目

`POST /api/projects`

Request:

```json
{
  "name": "episode_01",
  "source_language": "auto",
  "target_languages": ["en-US", "es-ES"],
  "translation_style": "short_drama_localized"
}
```

Response:

```json
{
  "project_id": "proj_123",
  "upload_url": "https://upload.example.com/..."
}
```

### 7.2 提交处理

`POST /api/projects/{project_id}/process`

Request:

```json
{
  "enable_source_separation": true,
  "enable_diarization": true,
  "generate_tts": false,
  "generate_preview_mp4": false,
  "agent_template": "subtitle_draft"
}
```

说明：

- generate_tts=false 时，系统只处理到翻译和字幕草稿。
- 建议 MVP 默认先到 proofreading，再由用户确认后生成 TTS。
- 接口成功后返回 agent_run_id。

Response:

```json
{
  "run_id": "run_123",
  "status": "pending"
}
```

### 7.3 查询 Agent Run

`GET /api/agent-runs/{run_id}`

Response:

```json
{
  "agent_run": {},
  "skill_runs": [],
  "current_checkpoint": "proofreading",
  "quality_flags": []
}
```

### 7.4 继续 Agent Run

`POST /api/agent-runs/{run_id}/continue`

Request:

```json
{
  "checkpoint": "proofreading",
  "confirmed": true
}
```

规则：

- 只能继续 waiting_human 状态的 run。
- 继续前必须保存用户编辑。

### 7.5 查询项目详情

`GET /api/projects/{project_id}`

Response:

```json
{
  "project": {},
  "tasks": [],
  "assets": [],
  "languages": ["en-US", "es-ES"]
}
```

### 7.6 查询句段

`GET /api/projects/{project_id}/segments?target_language=en-US`

Response:

```json
{
  "segments": [
    {
      "segment": {},
      "translation": {},
      "tts_job": {}
    }
  ]
}
```

### 7.7 更新句段和译文

`PATCH /api/projects/{project_id}/segments/{segment_id}`

Request:

```json
{
  "start_ms": 1200,
  "end_ms": 3600,
  "speaker_id": "spk_1",
  "translations": {
    "en-US": "What exactly do you want from me?"
  },
  "locked": true
}
```

规则：

- 只传需要修改的字段。
- 更新时间轴后，相关字幕和 TTS 标记为 stale。
- locked=true 后，自动翻译和自动分句不得覆盖该 segment。

### 7.8 生成或重跑目标语言

`POST /api/projects/{project_id}/generate`

Request:

```json
{
  "target_language": "en-US",
  "scope": "language",
  "steps": ["subtitle", "tts", "mix"],
  "segment_ids": [],
  "agent_template": "full_dubbing"
}
```

scope 枚举：

| scope | 说明 |
| --- | --- |
| language | 重跑整个目标语言 |
| segments | 只重跑指定句段 |
| package | 只重新打包 |

### 7.9 获取播放器 Manifest

`GET /api/projects/{project_id}/manifest?version_id=ver_001`

Response:

见 4.7 Manifest。

### 7.10 下载结果包

`POST /api/projects/{project_id}/packages`

Request:

```json
{
  "version_id": "ver_001",
  "languages": ["en-US", "es-ES"],
  "include_intermediate_assets": true
}
```

Response:

```json
{
  "package_id": "pkg_123",
  "status": "pending"
}
```

## 8. 文件命名规范

建议对象存储路径：

```text
projects/{project_id}/source/source.mp4
projects/{project_id}/source/source.wav
projects/{project_id}/separation/vocals.wav
projects/{project_id}/separation/background.wav
projects/{project_id}/asr/source_segments.json
projects/{project_id}/translations/{language}.json
projects/{project_id}/subtitles/{language}.srt
projects/{project_id}/subtitles/{language}.vtt
projects/{project_id}/tts/{language}/{segment_id}.wav
projects/{project_id}/audio/{language}.vocal.wav
projects/{project_id}/audio/{language}.mix.m4a
projects/{project_id}/preview/{language}.mp4
projects/{project_id}/packages/{version_id}.zip
```

## 9. 字幕生成规则

### 9.1 SRT

- 使用 segment start_ms/end_ms。
- 文本使用 active translation。
- 单条字幕建议不超过两行。
- 对过长翻译打 quality_flags。

### 9.2 WebVTT

- 用于网页播放器。
- 支持 source 和 target 语言。
- 不在 VTT 中放业务私有 JSON。

## 10. 音频生成规则

### 10.1 TTS 分段

- 每个 segment 生成一个 TTS 音频。
- TTS 输出保留原始文件。
- 拼接前做采样率和声道统一。

### 10.2 对齐

- 以 segment.start_ms 作为放置起点。
- 若 TTS 短于 segment 时长，可补静音。
- 若 TTS 长于 segment 时长，优先调整语速或提示人工修改译文。
- MVP 不做跨句复杂动态压缩。

### 10.3 混音

- background_audio 作为底轨。
- target_vocal 按时间轴叠加。
- 输出 target_mix_audio。
- 保留 source_audio 作为原音轨切换。

## 11. 模型适配器接口

### 11.1 ASR Adapter

Input:

```json
{
  "audio_asset_id": "asset_vocals",
  "source_language": "auto",
  "enable_diarization": true
}
```

Output:

```json
{
  "detected_language": "zh-CN",
  "segments": []
}
```

### 11.2 Translation Adapter

Input:

```json
{
  "source_language": "zh-CN",
  "target_language": "en-US",
  "segments": [],
  "style": "short_drama_localized",
  "glossary": {},
  "character_notes": []
}
```

Output:

```json
{
  "translations": [
    {
      "segment_id": "seg_0001",
      "text": "What exactly do you want from me?",
      "quality_flags": []
    }
  ],
  "model": "deepseek-default",
  "prompt_version": "short_drama_v1"
}
```

### 11.3 TTS Adapter

Input:

```json
{
  "target_language": "en-US",
  "text": "What exactly do you want from me?",
  "voice_id": "voice_en_female_01",
  "target_duration_ms": 2400,
  "speed": 1.0,
  "style": "dramatic"
}
```

Output:

```json
{
  "audio_asset_id": "asset_tts_0001",
  "actual_duration_ms": 2520,
  "provider": "minimax",
  "provider_task_id": "remote_123"
}
```

### 11.4 Source Separation Adapter

Input:

```json
{
  "audio_asset_id": "asset_source_audio",
  "mode": "vocal_background"
}
```

Output:

```json
{
  "source_vocal_asset_id": "asset_vocals",
  "background_asset_id": "asset_background",
  "quality_score": 0.78
}
```

## 12. 错误码

| error_code | 说明 |
| --- | --- |
| INVALID_VIDEO | 视频格式或编码不支持 |
| NO_AUDIO_TRACK | 视频没有可用音轨 |
| VIDEO_TOO_LONG | 视频超出 MVP 时长限制 |
| SOURCE_SEPARATION_FAILED | 声源分离失败 |
| ASR_FAILED | ASR 失败 |
| TRANSLATION_FAILED | 翻译失败 |
| TTS_FAILED | TTS 失败 |
| MIXING_FAILED | 混音失败 |
| PACKAGE_FAILED | 打包失败 |
| PROVIDER_RATE_LIMITED | 模型供应商限流 |
| PROVIDER_UNAVAILABLE | 模型供应商不可用 |
| AGENT_RUN_FAILED | Agent Run 执行失败 |
| SKILL_RUN_FAILED | Skill Run 执行失败 |
| HUMAN_CHECKPOINT_REQUIRED | 需要人工确认后继续 |

## 13. 安全要求

- 模型 API key 只能保存在服务端。
- 下载 URL 必须有过期时间或鉴权。
- 原视频和生成文件不得公开访问。
- 操作日志保留上传、编辑、生成、下载行为。
- 声音克隆能力默认关闭，启用前必须确认授权策略。
- Agent Runtime 不允许执行来自前端的任意代码。
- Skill Registry 不向前端返回密钥、私有 endpoint 或底层凭证。

## 14. 最小验收用例

### Case 1：中文到英文

- 上传 2 分钟中文短剧。
- 选择 en-US。
- 生成英文 VTT/SRT。
- 生成英文混合音轨。
- 网页可切换英文字幕和英文音轨。

### Case 2：英文到西语

- 上传 1 分钟英文短剧。
- 选择 es-ES。
- 生成人声替换音轨。
- 保留原 BGM。
- 下载结果包。

### Case 3：人工修改后重跑

- 修改某个 segment 的英文译文。
- 重跑该 segment 的 TTS。
- 重新混音。
- 预览页听到修改后的结果。
