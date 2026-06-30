/**
 * 单元测试：验证 Spec §3-§13 契约。
 * - 枚举值完整性
 * - Schema 接受 Spec 示例
 * - Schema 拒绝非法语言 / 非法状态 / 非法时间轴 / 未知错误码
 * - 路径生成符合 Spec §8
 */
import { describe, it, expect } from 'vitest'
import {
  // §3 语言
  LanguageCodeSchema,
  SourceLanguageSchema,
  TargetLanguageSchema,
  // §5/§4 枚举
  ProjectStatusSchema,
  TaskStatusSchema,
  AgentRunStatusSchema,
  TaskTypeSchema,
  AssetTypeSchema,
  AgentTemplateSchema,
  GenerateScopeSchema,
  // §12 错误码
  ErrorCodeSchema,
  // §4 实体
  ProjectSchema,
  MediaAssetSchema,
  SegmentSchema,
  TranslationSchema,
  SpeakerSchema,
  TTSJobSchema,
  ManifestSchema,
  AgentRunSchema,
  SkillRunSchema,
  SkillDefinitionSchema,
  // §6 Skill 契约
  SkillRequestEnvelopeSchema,
  SkillResponseEnvelopeSchema,
  successResponse,
  failureResponse,
  // §11 Adapter
  AsrAdapterInputSchema,
  AsrAdapterOutputSchema,
  TranslationAdapterInputSchema,
  TranslationAdapterOutputSchema,
  TtsAdapterInputSchema,
  TtsAdapterOutputSchema,
  SourceSeparationAdapterInputSchema,
  SourceSeparationAdapterOutputSchema,
  // §7 API DTO
  CreateProjectRequestSchema,
  CreateProjectResponseSchema,
  ProcessProjectRequestSchema,
  ProcessProjectResponseSchema,
  GetAgentRunResponseSchema,
  ContinueAgentRunRequestSchema,
  GetProjectResponseSchema,
  GetSegmentsResponseSchema,
  PatchSegmentRequestSchema,
  GenerateProjectRequestSchema,
  CreatePackageRequestSchema,
  CreatePackageResponseSchema,
  // §8 路径
  sourcePath,
  separationPath,
  asrPath,
  translationsPath,
  subtitlePath,
  ttsSegmentPath,
  audioPath,
  previewPath,
  packagePath,
} from '../src/index.js'

describe('§3 语言代码', () => {
  it('接受 zh-CN / en-US / es-ES / es-MX / pt-BR / auto 的语义边界', () => {
    for (const lang of ['zh-CN', 'en-US', 'es-ES', 'es-MX', 'pt-BR']) {
      expect(LanguageCodeSchema.safeParse(lang).success).toBe(true)
      expect(SourceLanguageSchema.safeParse(lang).success).toBe(true)
      expect(TargetLanguageSchema.safeParse(lang).success).toBe(true)
    }
    expect(SourceLanguageSchema.safeParse('auto').success).toBe(true)
  })

  it('auto 不能作为目标语言', () => {
    expect(TargetLanguageSchema.safeParse('auto').success).toBe(false)
  })

  it('拒绝非法语言代码', () => {
    expect(LanguageCodeSchema.safeParse('fr-FR').success).toBe(false)
    expect(SourceLanguageSchema.safeParse('ja-JP').success).toBe(false)
    expect(TargetLanguageSchema.safeParse('en').success).toBe(false)
  })
})

describe('§5 状态枚举值完整性', () => {
  it('ProjectStatus 与 Spec §5.1 一致', () => {
    expect(ProjectStatusSchema.options).toEqual([
      'draft', 'uploaded', 'planning', 'processing',
      'proofreading', 'generating', 'completed', 'failed', 'archived',
    ])
  })
  it('TaskStatus 与 Spec §5.2 一致', () => {
    expect(TaskStatusSchema.options).toEqual([
      'pending', 'running', 'succeeded', 'failed', 'canceled', 'retrying',
    ])
  })
  it('AgentRunStatus 与 Spec §5.3 一致', () => {
    expect(AgentRunStatusSchema.options).toEqual([
      'pending', 'planning', 'running', 'waiting_human', 'succeeded', 'failed', 'canceled',
    ])
  })
  it('TaskType 与 Spec §5.4 一致', () => {
    expect(TaskTypeSchema.options).toEqual([
      'probe_media', 'extract_audio', 'separate_sources', 'asr',
      'segment_normalize', 'translate', 'generate_subtitle', 'tts',
      'stitch_target_vocal', 'mix_audio', 'package_outputs',
    ])
  })
  it('拒绝非法状态', () => {
    expect(ProjectStatusSchema.safeParse('done').success).toBe(false)
    expect(TaskStatusSchema.safeParse('paused').success).toBe(false)
    expect(AgentRunStatusSchema.safeParse('waiting').success).toBe(false)
    expect(TaskTypeSchema.safeParse('unknown_step').success).toBe(false)
  })
  it('AssetType / AgentTemplate / GenerateScope 与 Spec 一致', () => {
    expect(AssetTypeSchema.options).toContain('target_mix_audio')
    expect(AgentTemplateSchema.options).toEqual([
      'subtitle_draft', 'full_dubbing', 'rerun_segments', 'package_only',
    ])
    expect(GenerateScopeSchema.options).toEqual(['language', 'segments', 'package'])
  })
})

describe('§12 错误码', () => {
  it('未知错误码不能通过 Schema 校验', () => {
    expect(ErrorCodeSchema.safeParse('UNKNOWN_ERROR').success).toBe(false)
    expect(ErrorCodeSchema.safeParse('TRANSLATION_FAILED').success).toBe(true)
  })
  it('覆盖 Spec §12 全部 14 个错误码', () => {
    expect(ErrorCodeSchema.options).toHaveLength(14)
    for (const code of [
      'INVALID_VIDEO', 'NO_AUDIO_TRACK', 'VIDEO_TOO_LONG', 'SOURCE_SEPARATION_FAILED',
      'ASR_FAILED', 'TRANSLATION_FAILED', 'TTS_FAILED', 'MIXING_FAILED', 'PACKAGE_FAILED',
      'PROVIDER_RATE_LIMITED', 'PROVIDER_UNAVAILABLE', 'AGENT_RUN_FAILED',
      'SKILL_RUN_FAILED', 'HUMAN_CHECKPOINT_REQUIRED',
    ]) {
      expect(ErrorCodeSchema.options).toContain(code)
    }
  })
})

describe('§4 核心实体 Schema 接受 Spec 示例', () => {
  it('Project §4.1', () => {
    expect(
      ProjectSchema.safeParse({
        project_id: 'proj_123',
        name: 'episode_01',
        status: 'processing',
        source_language: 'auto',
        target_languages: ['en-US', 'es-ES'],
        duration_ms: 128000,
        created_by: 'user_001',
        created_at: '2026-06-30T10:00:00Z',
        updated_at: '2026-06-30T10:03:00Z',
      }).success,
    ).toBe(true)
  })

  it('MediaAsset §4.2', () => {
    expect(
      MediaAssetSchema.safeParse({
        asset_id: 'asset_123',
        project_id: 'proj_123',
        type: 'source_video',
        language: null,
        uri: 's3://bucket/proj_123/source.mp4',
        format: 'mp4',
        duration_ms: 128000,
        size_bytes: 104857600,
        checksum: 'sha256:...',
        created_at: '2026-06-30T10:00:00Z',
      }).success,
    ).toBe(true)
  })

  it('Segment §4.3', () => {
    expect(
      SegmentSchema.safeParse({
        segment_id: 'seg_0001',
        project_id: 'proj_123',
        index: 1,
        start_ms: 1200,
        end_ms: 3600,
        speaker_id: 'spk_1',
        source_language: 'zh-CN',
        source_text: '你到底想怎么样？',
        asr_confidence: 0.92,
        locked: false,
        quality_flags: [],
      }).success,
    ).toBe(true)
  })

  it('Translation §4.4', () => {
    expect(
      TranslationSchema.safeParse({
        translation_id: 'tr_0001_en',
        segment_id: 'seg_0001',
        target_language: 'en-US',
        text: 'What exactly do you want from me?',
        style: 'short_drama_localized',
        model: 'deepseek-default',
        prompt_version: 'short_drama_v1',
        status: 'completed',
        edited_by: null,
        updated_at: '2026-06-30T10:05:00Z',
      }).success,
    ).toBe(true)
  })

  it('Speaker §4.5', () => {
    expect(
      SpeakerSchema.safeParse({
        speaker_id: 'spk_1',
        project_id: 'proj_123',
        display_name: 'Female Lead',
        source_voice_sample_asset_id: 'asset_voice_001',
        target_voice_map: {
          'en-US': 'voice_en_female_01',
          'es-ES': 'voice_es_female_01',
        },
      }).success,
    ).toBe(true)
  })

  it('TTSJob §4.6', () => {
    expect(
      TTSJobSchema.safeParse({
        tts_job_id: 'tts_123',
        project_id: 'proj_123',
        segment_id: 'seg_0001',
        target_language: 'en-US',
        text: 'What exactly do you want from me?',
        voice_id: 'voice_en_female_01',
        target_duration_ms: 2400,
        speed: 1.0,
        status: 'completed',
        output_asset_id: 'asset_tts_0001',
        actual_duration_ms: 2520,
        provider: 'minimax',
        provider_task_id: 'remote_123',
        error: null,
      }).success,
    ).toBe(true)
  })

  it('Manifest §4.7', () => {
    expect(
      ManifestSchema.safeParse({
        project_id: 'proj_123',
        version_id: 'ver_001',
        video: {
          url: 'https://cdn.example.com/proj_123/source.mp4',
          duration_ms: 128000,
        },
        subtitles: [
          { language: 'zh-CN', label: '中文原文', format: 'vtt', url: 'https://cdn.example.com/proj_123/source.zh-CN.vtt' },
          { language: 'en-US', label: 'English', format: 'vtt', url: 'https://cdn.example.com/proj_123/en-US.vtt' },
        ],
        audio_tracks: [
          { language: 'source', label: '原音轨', url: 'https://cdn.example.com/proj_123/source_audio.m4a' },
          { language: 'en-US', label: 'English Dub', url: 'https://cdn.example.com/proj_123/en-US.mix.m4a' },
        ],
        downloads: [
          { type: 'package_zip', label: '完整结果包', url: 'https://cdn.example.com/proj_123/package.zip' },
        ],
      }).success,
    ).toBe(true)
  })

  it('AgentRun §4.8', () => {
    expect(
      AgentRunSchema.safeParse({
        run_id: 'run_123',
        project_id: 'proj_123',
        version_id: 'ver_001',
        template: 'full_dubbing',
        status: 'running',
        current_step: 'localization.translate',
        source_language: 'auto',
        target_languages: ['en-US', 'es-ES'],
        created_by: 'user_001',
        created_at: '2026-06-30T10:01:00Z',
        updated_at: '2026-06-30T10:03:00Z',
      }).success,
    ).toBe(true)
  })

  it('SkillRun §4.9', () => {
    expect(
      SkillRunSchema.safeParse({
        skill_run_id: 'skillrun_123',
        run_id: 'run_123',
        project_id: 'proj_123',
        skill_name: 'localization.translate',
        skill_version: '1.0.0',
        status: 'succeeded',
        target_language: 'en-US',
        started_at: '2026-06-30T10:03:00Z',
        finished_at: '2026-06-30T10:03:30Z',
        input_refs: ['segver_001'],
        output_refs: ['trver_en_001'],
        provider: 'deepseek',
        model: 'deepseek-default',
        error: null,
      }).success,
    ).toBe(true)
  })

  it('SkillDefinition §4.10', () => {
    expect(
      SkillDefinitionSchema.safeParse({
        skill_name: 'voice.synthesize',
        skill_version: '1.0.0',
        enabled: true,
        default_provider: 'minimax',
        input_schema: 'VoiceSynthesizeInput',
        output_schema: 'VoiceSynthesizeOutput',
        timeout_seconds: 120,
        retry_limit: 2,
      }).success,
    ).toBe(true)
  })
})

describe('§4 非法时间轴被拒绝', () => {
  it('Segment start_ms 必须 < end_ms', () => {
    expect(
      SegmentSchema.safeParse({
        segment_id: 'seg_0001',
        project_id: 'proj_123',
        index: 1,
        start_ms: 3600,
        end_ms: 1200,
        speaker_id: 'spk_1',
        source_language: 'zh-CN',
        source_text: 'x',
        asr_confidence: null,
        locked: false,
        quality_flags: [],
      }).success,
    ).toBe(false)
  })
  it('PatchSegment 同时传 start/end 时 start 必须 < end', () => {
    expect(PatchSegmentRequestSchema.safeParse({ start_ms: 3600, end_ms: 1200 }).success).toBe(false)
    expect(PatchSegmentRequestSchema.safeParse({ start_ms: 1200, end_ms: 3600 }).success).toBe(true)
    expect(PatchSegmentRequestSchema.safeParse({ locked: true }).success).toBe(true)
  })
})

describe('§6 Skill 调用契约', () => {
  it('Request 信封接受 Spec §6 示例', () => {
    expect(
      SkillRequestEnvelopeSchema.safeParse({
        skill_name: 'localization.translate',
        skill_version: '1.0.0',
        project_id: 'proj_123',
        run_id: 'run_123',
        input: {},
        config: {},
        idempotency_key: 'run_123:localization.translate:en-US:v1',
      }).success,
    ).toBe(true)
  })

  it('Success Response 信封接受 Spec §6 示例', () => {
    expect(
      SkillResponseEnvelopeSchema.safeParse({
        status: 'succeeded',
        outputs: {},
        assets: [],
        quality_flags: [],
        usage: { provider: 'deepseek', model: 'deepseek-default', tokens: 1200, cost: null },
        error: null,
      }).success,
    ).toBe(true)
  })

  it('Failure Response 信封接受 Spec §6 示例（未知错误码被拒绝）', () => {
    expect(
      SkillResponseEnvelopeSchema.safeParse({
        status: 'failed',
        outputs: {},
        assets: [],
        quality_flags: [],
        usage: {},
        error: { code: 'TRANSLATION_FAILED', message: 'Provider request failed' },
      }).success,
    ).toBe(true)
    expect(
      SkillResponseEnvelopeSchema.safeParse({
        status: 'failed',
        outputs: {},
        assets: [],
        quality_flags: [],
        usage: {},
        error: { code: 'NOT_A_REAL_CODE', message: 'x' },
      }).success,
    ).toBe(false)
  })

  it('successResponse / failureResponse 工厂产出合法结构', () => {
    const ok = successResponse({ translated: 1 }, {
      usage: { provider: 'deepseek', model: 'm', tokens: 10, cost: null },
    })
    expect(ok.status).toBe('succeeded')
    expect(ok.error).toBeNull()
    expect(SkillResponseEnvelopeSchema.safeParse(ok).success).toBe(true)

    const fail = failureResponse({ code: 'TTS_FAILED', message: 'boom' })
    expect(fail.status).toBe('failed')
    expect(fail.error.code).toBe('TTS_FAILED')
    expect(SkillResponseEnvelopeSchema.safeParse(fail).success).toBe(true)
  })
})

describe('§11 Adapter 类型', () => {
  it('ASR Adapter §11.1', () => {
    expect(
      AsrAdapterInputSchema.safeParse({
        audio_asset_id: 'asset_vocals',
        source_language: 'auto',
        enable_diarization: true,
      }).success,
    ).toBe(true)
    expect(
      AsrAdapterOutputSchema.safeParse({
        detected_language: 'zh-CN',
        segments: [],
      }).success,
    ).toBe(true)
  })

  it('Translation Adapter §11.2', () => {
    expect(
      TranslationAdapterInputSchema.safeParse({
        source_language: 'zh-CN',
        target_language: 'en-US',
        segments: [],
        style: 'short_drama_localized',
        glossary: {},
        character_notes: [],
      }).success,
    ).toBe(true)
    expect(
      TranslationAdapterOutputSchema.safeParse({
        translations: [
          { segment_id: 'seg_0001', text: 'What exactly do you want from me?', quality_flags: [] },
        ],
        model: 'deepseek-default',
        prompt_version: 'short_drama_v1',
      }).success,
    ).toBe(true)
  })

  it('TTS Adapter §11.3', () => {
    expect(
      TtsAdapterInputSchema.safeParse({
        target_language: 'en-US',
        text: 'What exactly do you want from me?',
        voice_id: 'voice_en_female_01',
        target_duration_ms: 2400,
        speed: 1.0,
        style: 'dramatic',
      }).success,
    ).toBe(true)
    expect(
      TtsAdapterOutputSchema.safeParse({
        audio_asset_id: 'asset_tts_0001',
        actual_duration_ms: 2520,
        provider: 'minimax',
        provider_task_id: 'remote_123',
      }).success,
    ).toBe(true)
  })

  it('Source Separation Adapter §11.4', () => {
    expect(
      SourceSeparationAdapterInputSchema.safeParse({
        audio_asset_id: 'asset_source_audio',
        mode: 'vocal_background',
      }).success,
    ).toBe(true)
    expect(
      SourceSeparationAdapterOutputSchema.safeParse({
        source_vocal_asset_id: 'asset_vocals',
        background_asset_id: 'asset_background',
        quality_score: 0.78,
      }).success,
    ).toBe(true)
  })
})

describe('§7 API DTO 接受 Spec 示例', () => {
  it('CreateProject §7.1', () => {
    expect(
      CreateProjectRequestSchema.safeParse({
        name: 'episode_01',
        source_language: 'auto',
        target_languages: ['en-US', 'es-ES'],
        translation_style: 'short_drama_localized',
      }).success,
    ).toBe(true)
    expect(
      CreateProjectResponseSchema.safeParse({
        project_id: 'proj_123',
        upload_url: 'https://upload.example.com/abc',
      }).success,
    ).toBe(true)
  })

  it('ProcessProject §7.2', () => {
    expect(
      ProcessProjectRequestSchema.safeParse({
        enable_source_separation: true,
        enable_diarization: true,
        generate_tts: false,
        generate_preview_mp4: false,
        agent_template: 'subtitle_draft',
      }).success,
    ).toBe(true)
    expect(
      ProcessProjectResponseSchema.safeParse({ run_id: 'run_123', status: 'pending' }).success,
    ).toBe(true)
  })

  it('GetAgentRun §7.3 / ContinueAgentRun §7.4', () => {
    expect(
      GetAgentRunResponseSchema.safeParse({
        agent_run: {
          run_id: 'run_123', project_id: 'proj_123', version_id: 'ver_001',
          template: 'full_dubbing', status: 'running',
          current_step: 'localization.translate', source_language: 'auto',
          target_languages: ['en-US'], created_by: 'user_001',
          created_at: '2026-06-30T10:01:00Z', updated_at: '2026-06-30T10:03:00Z',
        },
        skill_runs: [],
        current_checkpoint: 'proofreading',
        quality_flags: [],
      }).success,
    ).toBe(true)
    expect(
      ContinueAgentRunRequestSchema.safeParse({ checkpoint: 'proofreading', confirmed: true })
        .success,
    ).toBe(true)
  })

  it('GetProject §7.5 / GetSegments §7.6', () => {
    expect(
      GetProjectResponseSchema.safeParse({
        project: {
          project_id: 'proj_123', name: 'ep', status: 'processing',
          source_language: 'auto', target_languages: ['en-US'],
          duration_ms: 1000, created_by: 'u', created_at: '2026-06-30T10:00:00Z',
          updated_at: '2026-06-30T10:00:00Z',
        },
        tasks: [],
        assets: [],
        languages: ['en-US'],
      }).success,
    ).toBe(true)
    expect(GetSegmentsResponseSchema.safeParse({ segments: [] }).success).toBe(true)
  })

  it('GenerateProject §7.8', () => {
    expect(
      GenerateProjectRequestSchema.safeParse({
        target_language: 'en-US',
        scope: 'language',
        steps: ['subtitle', 'tts', 'mix'],
        segment_ids: [],
        agent_template: 'full_dubbing',
      }).success,
    ).toBe(true)
    expect(
      GenerateProjectRequestSchema.safeParse({
        target_language: 'en-US', scope: 'language', steps: ['unknown'], segment_ids: [], agent_template: 'full_dubbing',
      }).success,
    ).toBe(false)
  })

  it('CreatePackage §7.10', () => {
    expect(
      CreatePackageRequestSchema.safeParse({
        version_id: 'ver_001',
        languages: ['en-US', 'es-ES'],
        include_intermediate_assets: true,
      }).success,
    ).toBe(true)
    expect(
      CreatePackageResponseSchema.safeParse({ package_id: 'pkg_123', status: 'pending' }).success,
    ).toBe(true)
  })
})

describe('§8 文件路径生成', () => {
  const pid = 'proj_123'
  it('source', () => {
    expect(sourcePath(pid, 'mp4')).toBe('projects/proj_123/source/source.mp4')
    expect(sourcePath(pid, 'wav')).toBe('projects/proj_123/source/source.wav')
  })
  it('separation', () => {
    expect(separationPath(pid, 'vocals')).toBe('projects/proj_123/separation/vocals.wav')
    expect(separationPath(pid, 'background')).toBe('projects/proj_123/separation/background.wav')
  })
  it('asr', () => {
    expect(asrPath(pid)).toBe('projects/proj_123/asr/source_segments.json')
  })
  it('translations', () => {
    expect(translationsPath(pid, 'en-US')).toBe('projects/proj_123/translations/en-US.json')
  })
  it('subtitles', () => {
    expect(subtitlePath(pid, 'en-US', 'srt')).toBe('projects/proj_123/subtitles/en-US.srt')
    expect(subtitlePath(pid, 'en-US', 'vtt')).toBe('projects/proj_123/subtitles/en-US.vtt')
  })
  it('tts segment', () => {
    expect(ttsSegmentPath(pid, 'en-US', 'seg_0001')).toBe('projects/proj_123/tts/en-US/seg_0001.wav')
  })
  it('audio', () => {
    expect(audioPath(pid, 'en-US', 'vocal')).toBe('projects/proj_123/audio/en-US.vocal.wav')
    expect(audioPath(pid, 'en-US', 'mix')).toBe('projects/proj_123/audio/en-US.mix.m4a')
  })
  it('preview', () => {
    expect(previewPath(pid, 'en-US')).toBe('projects/proj_123/preview/en-US.mp4')
  })
  it('packages', () => {
    expect(packagePath(pid, 'ver_001')).toBe('projects/proj_123/packages/ver_001.zip')
  })
})
